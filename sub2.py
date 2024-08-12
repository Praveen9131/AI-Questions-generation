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
image_store_sub2 = {}

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
        image_key = f"image_{len(image_store_sub2) + 1}.png"
        image_store_sub2[image_key] = output
        return image_key
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        if retries > 0:
            logger.info(f"Retrying download and resize, {retries} retries left.")
            return download_and_resize_image(image_url, target_size, retries - 1)
        return None

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

def parse_correct_answers(correct_answers_section):
    """Parse the correct answers section to extract indices."""
    try:
        return [int(index.strip()) - 1 for index in correct_answers_section.split(',')]
    except ValueError as e:
        logger.error(f"Error parsing correct answers: {e}")
        return []

def generate_mcq(subject: str, tone: str):
    """Generate a multiple-choice question with a single correct answer based on the subject."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a clear and understandable question with exactly four options based on the subject '{subject}'. The question must have exactly one correct answer. Each option should be related to the concept in the subject and in a '{tone}' tone. Use the following format:\n\n**Question:** [Question based on the subject]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n3. [Option 3]\n4. [Option 4]\n\n**Correct Answer:** [Correct Option number]\n\nEnsure that all four options are provided, and the correct answer should be just a number (1, 2, 3, or 4)."}
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
        options_section = content.split("**Options:**")[1].split("**Correct Answer:**")[0].strip()
        correct_answer_section = content.split("**Correct Answer:**")[1].strip()

        # Extracting options
        options = options_section.split('\n')
        if len(options) != 4:
            raise ValueError("Generated options do not contain exactly 4 items")

        option_prompts = [option.split('. ', 1)[1].strip() for option in options]

        # Extracting the correct answer index and ensuring it's a valid integer
        correct_answer_index = None
        try:
            correct_answer_index = int(correct_answer_section.strip())
            if correct_answer_index < 1 or correct_answer_index > 4:
                raise ValueError("Correct answer index out of range")
        except ValueError:
            logger.error(f"Correct answer section could not be parsed as an integer: {correct_answer_section}")
            return {"error": "Failed to parse correct answer"}

        correct_answers = [f"Option {correct_answer_index}"]

        return {
            "question": question_section,
            "options": option_prompts,
            "correct_answer": correct_answers
        }
    except Exception as e:
        logger.error(f"Error generating MCQ: {e}")
        return {"error": "Failed to generate MCQ"}

def generate_custom_content_sub2(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 10:  # Ensure number is within allowed range
            return {"error": "Number of questions must be between 1 and 10"}, 400

        main_prompt = f"Generate a main question with context for the following subject: {subject}"
        main_question_response = generate_mcq(subject, tone)
        if "error" in main_question_response:
            return {"error": "Failed to generate main question"}, 500
        
        main_image_url = generate_image(subject)
        main_image_key = download_and_resize_image(main_image_url, (750, 319)) if main_image_url else "placeholder_image_url"
        if main_image_key == "placeholder_image_url":
            return {"error": "Failed to generate main image"}, 500

        questions = []
        for _ in range(number):
            sub_questions = []
            for sub_idx in range(3):  # Each question has exactly 3 sub-questions
                sub_question = generate_mcq(subject, tone)
                if not sub_question:
                    return {"error": f"Failed to generate sub-question {sub_idx + 1}"}, 500
                sub_questions.append(sub_question)

            questions.append({
                "main_question": main_question_response["question"],
                "image": f"/image/{main_image_key}",
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
                        "correct_answer": sub_question["correct_answer"]
                    }
                })
            elif content_type == 'image':
                image_prompt = sub_question.get("question", "")
                image_url = generate_image(image_prompt)
                image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"  # Option image size: 270x140 px
                sub_question_formatted.append({
                    f"Sub Question No. {sub_idx + 1}": {
                        "image": f"/image/{image_key}",
                        "options": sub_question["options"],
                        "correct_answer": sub_question["correct_answer"]
                    }
                })
            else:  # text_with_image
                image_prompt = sub_question.get("question", "")
                image_url = generate_image(image_prompt)
                image_key = download_and_resize_image(image_url, (270, 140)) if image_url else "placeholder_image_url"  # Option image size: 270x140 px
                sub_question_formatted.append({
                    f"Sub Question No. {sub_idx + 1}": {
                        "question": sub_question.get("question", ""),
                        "image": f"/image/{image_key}",
                        "options": sub_question["options"],
                        "correct_answer": sub_question["correct_answer"]
                    }
                })
        formatted_questions.append({
            "main_question": question["main_question"],
            "image": question["image"],
            "sub_questions": sub_question_formatted
        })
    return formatted_questions

@app.route('/custom', methods=['POST'])
def custom_content():
    """Endpoint to generate custom content based on user-provided parameters."""
    try:
        data = request.json
        num_questions = int(data.get('number', 1))
        subject = data.get('subject', 'default subject').strip('"')
        tone = data.get('tone', 'neutral')

        result = generate_custom_content_sub2(num_questions, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in custom content generation: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/', methods=['GET', 'POST'])
def generate_content():
    """Endpoint to generate content based on user-set parameters."""
    try:
        if request.method == 'POST':
            data = request.json 
            num_questions = int(data.get('number', 1))
            subject = data.get('subject', 'default subject').strip('"')
            tone = data.get('tone', 'neutral')
        else:
            num_questions = int(request.args.get('number', 1))
            subject = request.args.get('subject', 'default subject').strip('"')
            tone = request.args.get('tone', 'neutral')

        result = generate_custom_content_sub2(num_questions, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Endpoint to retrieve an image by its key."""
    try:
        image = image_store_sub2.get(image_key)
        if not image:
            return jsonify({"error": "Image not found"}), 404
        return send_file(image, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error retrieving image: {e}")
        return jsonify({"error": "Internal server error"}), 500

