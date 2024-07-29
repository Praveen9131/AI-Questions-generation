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
image_store_checkbox = {}

def download_and_resize_image(image_url, target_size):
    """Download an image from the given URL, resize it, and store it in-memory."""
    try:
        logger.info(f"Downloading image from URL: {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        resized_image = image.resize(target_size, Image.LANCZOS)
        output = BytesIO()
        resized_image.save(output, format='PNG')
        output.seek(0)
        image_key = f"image_{len(image_store_checkbox) + 1}.png"
        image_store_checkbox[image_key] = output
        return image_key
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
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
            # Modify prompt slightly for retry
            modified_prompt = f"{prompt}, in a different style"
            return generate_image(modified_prompt, retries - 1)
        return None

def generate_mcq_with_image_options(subject: str, tone: str):
    """Generate a checkbox question with images as options based on the subject."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a clear and understandable question with exactly four options based on the subject '{subject}'. The question may have two to four correct answers. Each option should be related to the concept in the subject and in a '{tone}' tone. Use the following format:\n\n**Question:** [Question based on the subject]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n3. [Option 3]\n4. [Option 4]\n\n**Correct Answers:** [Correct Options by number, separated by commas]\n\nEnsure that all four options are provided."}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=description_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        content = response.choices[0].message.content

        question_section = content.split("**Question:**")[1].split("**Options:**")[0].strip()
        options_section = content.split("**Options:**")[1].split("**Correct Answers:**")[0].strip()
        correct_answers_section = content.split("**Correct Answers:**")[1].strip()

        options = options_section.split('\n')
        if len(options) != 4:
            raise ValueError("Generated options do not contain exactly 4 items")

        option_prompts = [option.split('. ', 1)[1].strip() for option in options]
        
        # Extracting correct answer indices
        correct_answer_indices = [int(index.strip()) - 1 for index in correct_answers_section.split(',')]
        
        # Ensure the number of correct answers is between 2 and 4
        if len(correct_answer_indices) < 2:
            additional_indices = list(set(range(4)) - set(correct_answer_indices))
            correct_answer_indices += random.sample(additional_indices, 2 - len(correct_answer_indices))
        elif len(correct_answer_indices) > 4:
            correct_answer_indices = random.sample(correct_answer_indices, 4)
        
        correct_answers = [option_prompts[i] for i in correct_answer_indices]

        option_images = generate_image_options(option_prompts)

        # If image generation failed, retry with a new question
        if len(option_images) != 4 or "placeholder_image_url" in option_images:
            logger.warning("Not all option images were generated successfully. Retrying with a new question.")
            return generate_mcq_with_image_options(subject, tone)  # Retry with a new question

        options_and_images = list(zip(option_prompts, option_images))
        random.shuffle(options_and_images)
        shuffled_option_prompts, shuffled_option_images = zip(*options_and_images)

        shuffled_correct_answers = [
            f"Option {shuffled_option_prompts.index(ans) + 1}"
            for ans in correct_answers
        ]

        return {
            "question": question_section,
            "options": {
                f"Option {i+1}": img for i, img in enumerate(shuffled_option_images)
            },
            "correct_answers": shuffled_correct_answers
        }
    except Exception as e:
        logger.error(f"Error generating MCQ with image options: {e}")
        return {"error": "Failed to generate MCQ"}

def generate_image_options(prompts):
    """Generate multiple images based on a list of prompts."""
    options = []
    for prompt in prompts:
        image_url = generate_image(prompt)
        if image_url:
            options.append(image_url)
        else:
            logger.error(f"Failed to generate image for prompt: {prompt}")
            options.append("placeholder_image_url")
    return options

def generate_custom_content_checkbox(number, subject, tone):
    """Generate custom content based on user-provided parameters with retries."""
    try:
        if number < 1 or number > 10:  # Ensure number is within allowed range
            return {"error": "Number of questions must be between 1 and 10"}, 400

        images_and_questions = []
        for _ in range(number):
            image_prompt = f"High-quality, detailed illustration representing the subject: {subject} in a {tone} tone"
            question_image_url = generate_image(image_prompt)
            
            # Retry logic if placeholder image URL is set
            if question_image_url == "placeholder_image_url":
                question_image_url = generate_image(image_prompt + " illustration", retries=1)
            
            if not question_image_url:
                question_image_url = "placeholder_image_url"

            mcq_with_images = generate_mcq_with_image_options(subject, tone)
            if "error" in mcq_with_images:
                return {"error": "Failed to generate MCQ"}, 500

            mcq_with_images["question_image_url"] = question_image_url
            images_and_questions.append(mcq_with_images)

        for item in images_and_questions:
            question_image_url = item["question_image_url"]
            question_image_key = download_and_resize_image(question_image_url, (750, 319)) if question_image_url != "placeholder_image_url" else "placeholder_image_url"
            if question_image_key:
                item["question_image_url"] = f"/image/{question_image_key}"

            for option_key in item["options"]:
                option_image_url = item["options"][option_key]
                option_image_key = download_and_resize_image(option_image_url, (270, 140)) if option_image_url != "placeholder_image_url" else "placeholder_image_url"
                if option_image_key:
                    item["options"][option_key] = f"/image/{option_image_key}"

        return images_and_questions
    except Exception as e:
        logger.error(f"Error generating custom content: {e}")
        return {"error": "Internal server error"}, 500

@app.route('/custom', methods=['POST'])
def custom_content():
    """Endpoint to generate custom content based on user-provided parameters."""
    try:
        data = request.json
        num_questions = int(data.get('number', 1))
        subject = data.get('subject', 'default subject').strip('"')
        tone = data.get('tone', 'neutral')

        result = generate_custom_content_checkbox(num_questions, subject, tone)
        
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

        if num_questions < 1 or num_questions > 10:
            return jsonify({"error": "Number of questions must be between 1 and 10"}), 400

        images_and_questions = []
        for _ in range(num_questions):
            image_prompt = f"High-quality, detailed illustration representing the subject: {subject} in a {tone} tone"
            question_image_url = generate_image(image_prompt)
            if not question_image_url:
                question_image_url = "placeholder_image_url"

            mcq_with_images = generate_mcq_with_image_options(subject, tone)
            if "error" in mcq_with_images:
                return jsonify(mcq_with_images), 500

            mcq_with_images["question_image_url"] = question_image_url
            images_and_questions.append(mcq_with_images)

        for item in images_and_questions:
            question_image_url = item["question_image_url"]
            question_image_key = download_and_resize_image(question_image_url, (750, 319)) if question_image_url != "placeholder_image_url" else "placeholder_image_url"
            if question_image_key:
                item["question_image_url"] = f"/image/{question_image_key}"

            for option_key in item["options"]:
                option_image_url = item["options"][option_key]
                option_image_key = download_and_resize_image(option_image_url, (270, 140)) if option_image_url != "placeholder_image_url" else "placeholder_image_url"
                if option_image_key:
                    item["options"][option_key] = f"/image/{option_image_key}"

        return jsonify(images_and_questions)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Serve an image from in-memory storage."""
    if image_key in image_store_checkbox:
        return send_file(
            BytesIO(image_store_checkbox[image_key].getvalue()),
            mimetype='image/png'
        )
    else:
        logger.error(f"Image with key {image_key} not found")
        return jsonify({"error": "Image not found"}), 404