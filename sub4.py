import os
import logging
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from PIL import Image
import requests
from io import BytesIO
from openai import OpenAI
import random

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.error("OPENAI_API_KEY environment variable not set")
    exit()

# Initialize OpenAI client with API key
client = OpenAI(api_key=openai_api_key)

app = Flask(__name__)

# In-memory storage for images
image_store_sub4 = {}

def download_and_resize_image(image_url, target_size, retries=3):
    """Download an image from the given URL, resize it, and store it in-memory with retry logic."""
    try:
        logger.info(f"Downloading image from URL: {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        resized_image = image.resize(target_size, Image.LANCZOS)
        output = BytesIO()
        resized_image.save(output, format='PNG')
        output.seek(0)
        image_key = f"image_{len(image_store_sub4) + 1}.png"
        image_store_sub4[image_key] = output
        return image_key
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        if retries > 0:
            logger.info(f"Retrying download and resize, {retries} retries left.")
            return download_and_resize_image(image_url, target_size, retries - 1)
        return "placeholder_image_url"

def generate_image(prompt: str, retries: int = 3):
    """Generate an image using the DALL-E model from OpenAI, with retry logic."""
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        safe_prompt = f"An illustration of {prompt} in a simple, neutral style"
        response = client.images.generate(
            model="dall-e-3",
            prompt=safe_prompt,
            n=1,
            size="1024x1024"
        )
        return response.data[0].url if response.data else None
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        if retries > 0:
            logger.info(f"Retrying image generation, {retries} retries left.")
            modified_prompt = f"{prompt}, in a different style"
            return generate_image(modified_prompt, retries - 1)
        return None

def generate_mcq(subject: str, tone: str):
    """Generate a checkbox question with multiple correct answers and image options based on the subject."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a clear and understandable checkbox question with exactly four options based on the subject '{subject}'. The question must have more than one correct answer. Each option should be related to the concept in the subject and in a '{tone}' tone. Use the following format:\n\n**Question:** [Question based on the subject]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n3. [Option 3]\n4. [Option 4]\n\n**Correct Answers:** [Correct Option numbers separated by commas]\n\nEnsure that all four options are provided, and the correct answers should be a comma-separated list of numbers (e.g., 1, 3)."}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=description_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        content = response.choices[0].message.content

        # Parsing the response
        question_section = content.split("**Question:**")[1].split("**Options:**")[0].strip()
        options_section = content.split("**Options:**")[1].split("**Correct Answers:**")[0].strip()
        correct_answers_section = content.split("**Correct Answers:**")[1].strip()

        # Extracting options
        options = options_section.split('\n')
        if len(options) != 4:
            raise ValueError("Generated options do not contain exactly 4 items")

        option_prompts = [option.split('. ', 1)[1].strip() for option in options]

        # Extracting the correct answer indices and ensuring they are valid integers
        try:
            correct_answer_indices = [int(x.strip()) for x in correct_answers_section.split(',')]
            if not all(1 <= idx <= 4 for idx in correct_answer_indices):
                raise ValueError("One or more correct answer indices are out of range")
        except ValueError:
            logger.error(f"Correct answers section could not be parsed as integers: {correct_answers_section}")
            return {"error": "Failed to parse correct answers"}

        correct_answers = [f"Option {idx}" for idx in correct_answer_indices]

        # Generate the main question image (750x319 px)
        main_image_url = generate_image(question_section)
        main_image_key = download_and_resize_image(main_image_url, (750, 319)) if main_image_url else "placeholder_image_url"
        
        # Retry if a placeholder image was returned
        if main_image_key == "placeholder_image_url":
            logger.info("Retrying main image generation due to placeholder.")
            main_image_url = generate_image(question_section)
            main_image_key = download_and_resize_image(main_image_url, (750, 319)) if main_image_url else "placeholder_image_url"

        if main_image_key == "placeholder_image_url":
            return {"error": "Failed to generate main image after retries"}, 500

        # Generate images for each option (270x140 px)
        option_images = {}
        for idx, prompt in enumerate(option_prompts, start=1):
            image_url = generate_image(prompt)
            image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"
            
            # Retry if a placeholder image was returned
            if image_key == "placeholder_image_url":
                logger.info(f"Retrying image generation for option {idx} due to placeholder.")
                image_url = generate_image(prompt)
                image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"

            if image_key == "placeholder_image_url":
                logger.error(f"Failed to store image for option {idx} after retries.")
                return {"error": f"Failed to store image for option {idx} after retries"}, 500
            
            option_images[f"Option {idx}"] = f"/image/{image_key}"

        return {
            "question": question_section,
            "main_image": f"/image/{main_image_key}",
            "options": option_images,  # Return labeled image URLs
            "correct_answers": correct_answers
        }
    except Exception as e:
        logger.error(f"Error generating MCQ: {e}")
        return {"error": "Failed to generate MCQ"}

@app.route('/custom', methods=['GET', 'POST'])
def custom_content():
    """Endpoint to generate custom content based on user-provided parameters."""
    try:
        if request.method == 'POST':
            data = request.json
            num_questions = int(data.get('number', 1))
            subject = data.get('subject', 'default subject').strip('"')
            tone = data.get('tone', 'neutral')
        else:  # For GET method
            num_questions = int(request.args.get('number', 1))
            subject = request.args.get('subject', 'default subject').strip('"')
            tone = request.args.get('tone', 'neutral')

        result = generate_custom_content_sub4(num_questions, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in custom content generation: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Endpoint to retrieve an image by its key."""
    try:
        image = image_store_sub4.get(image_key)
        if not image:
            return jsonify({"error": "Image not found"}), 404
        return send_file(image, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error retrieving image: {e}")
        return jsonify({"error": "Internal server error"}), 500

def generate_custom_content_sub4(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 100:  # Ensure number is within allowed range
            return {"error": "Number of questions must be between 1 and 10"}, 400

        main_question_response = generate_mcq(subject, tone)
        if "error" in main_question_response:
            return {"error": "Failed to generate main question"}, 500
        
        questions = []
        for _ in range(number):
            sub_questions = []
            for sub_idx in range(2):  # Updated to generate exactly 2 sub-questions
                sub_question = generate_mcq(subject, tone)
                # Ensure that sub-questions always include the "question" key
                if not sub_question.get("question"):
                    sub_question["question"] = main_question_response["question"]
                if not sub_question:
                    return {"error": f"Failed to generate sub-question {sub_idx + 1}"}, 500
                sub_questions.append(sub_question)

            questions.append({
                "main_question": main_question_response["question"],
                "image": main_question_response["main_image"],
                "sub_questions": sub_questions
            })

        return format_questions_as_sections(questions)
    except Exception as e:
        logger.error(f"Error generating custom content: {e}")
        return {"error": "Internal server error"}, 500

def format_questions_as_sections(questions):
    """Format questions in the specified structure."""
    formatted_questions = []
    for idx, question in enumerate(questions):
        sub_question_formatted = []
        for sub_idx, sub_question in enumerate(question["sub_questions"]):
            content_type = random.choice(['text', 'image', 'text_with_image'])
            if content_type == 'text':
                sub_question_formatted.append({
                    f"Sub Question No. {sub_idx + 1}": {
                        "question": sub_question.get("question", ""),
                        "options": sub_question["options"],
                        "correct_answers": sub_question["correct_answers"]
                    }
                })
            elif content_type == 'image':
                image_prompt = sub_question.get("question", "")
                image_url = generate_image(image_prompt)
                image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"  # Option image size: 270x140 px
                if image_key == "placeholder_image_url":
                    logger.info(f"Retrying image generation for sub-question {sub_idx + 1} due to placeholder.")
                    image_url = generate_image(image_prompt)
                    image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"

                sub_question_formatted.append({
                    f"Sub Question No. {sub_idx + 1}": {
                        "image": f"/image/{image_key}",
                        "options": sub_question["options"],
                        "correct_answers": sub_question["correct_answers"]
                    }
                })
            else:  # text_with_image
                image_prompt = sub_question.get("question", "")
                image_url = generate_image(image_prompt)
                image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"  # Option image size: 270x140 px
                if image_key == "placeholder_image_url":
                    logger.info(f"Retrying image generation for sub-question {sub_idx + 1} due to placeholder.")
                    image_url = generate_image(image_prompt)
                    image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"

                sub_question_formatted.append({
                    f"Sub Question No. {sub_idx + 1}": {
                        "question": sub_question.get("question", ""),
                        "image": f"/image/{image_key}",
                        "options": sub_question["options"],
                        "correct_answers": sub_question["correct_answers"]
                    }
                })
        formatted_questions.append({
            "main_question": question["main_question"],
            "image": question["image"],
            "sub_questions": sub_question_formatted
        })
    return formatted_questions


