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
image_store_appro = {}

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
        image_key = f"image_{len(image_store_appro) + 1}.png"
        image_store_appro[image_key] = output
        return image_key
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return None

def generate_image(prompt: str):
    """Generate an image using the DALL-E model from OpenAI."""
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        safe_prompt = f"Simple, non-offensive illustration of {prompt}"
        response = client.images.generate(
            model="dall-e-3",
            prompt=safe_prompt,
            n=1,
            size="1024x1024"
        )
        return response.data[0].url
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

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

def generate_mcq_with_image_options(subject: str, tone: str):
    """Generate a multiple-choice question with images as options based on the subject."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a clear and understandable multiple-choice question with exactly two options based on the subject '{subject}'. Each option should be related to the concept in the subject and in a '{tone}' tone. Ensure that one option is 'least appropriate' and the other is 'most appropriate'. Provide a detailed situation followed by the question. Use the following format:\n\n**Question Text:** [Detailed situation explaining the context. Your fears were confirmed when colleagues started calling you names that are obviously a reference to your ethnic origin. Your confidence is low, you felt humiliated and physically sick. The suggested responses; [Question based on the situation]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n\n**Correct Answers:**\n- Least Appropriate: [Option 1]\n- Most Appropriate: [Option 2]\n\nEnsure that both options are provided with appropriate labels."}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=description_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        content = response.choices[0].message.content.strip()

        # Extract question, options, and correct answers
        question_text = content.split("**Question Text:**")[1].split("**Options:**")[0].strip()
        options_section = content.split("**Options:**")[1].split("**Correct Answers:**")[0].strip()
        correct_answers_text = content.split("**Correct Answers:**")[1].strip()

        # Parse options
        options = [option.split('. ')[1] for option in options_section.split('\n') if option.strip()]
        correct_answers = {}
        for line in correct_answers_text.split('\n'):
            if 'Least Appropriate' in line:
                correct_answers['least_appropriate'] = line.split(': ')[1].strip()
            elif 'Most Appropriate' in line:
                correct_answers['most_appropriate'] = line.split(': ')[1].strip()

        if len(options) != 2:
            logger.error(f"Invalid number of options: {len(options)}")
            return {"error": "Invalid number of options"}, 500

        # Generate images for each option
        option_images = generate_image_options(options)
        if "placeholder_image_url" in option_images:
            return {"error": "Failed to generate some images"}, 500

        # Generate image filenames
        question_images = []
        for image_url in option_images:
            image_key = download_and_resize_image(image_url, (270, 140)) if image_url != "placeholder_image_url" else "placeholder_image_url"
            if image_key:
                question_images.append(image_key)

        return {
            "question_text": question_text,
            "options": [
                {
                    "least_appropriate": options[0] == correct_answers.get('least_appropriate', ''),
                    "most_appropriate": options[0] == correct_answers.get('most_appropriate', ''),
                    "option_id": "A",
                    "text": options[0]
                },
                {
                    "least_appropriate": options[1] == correct_answers.get('least_appropriate', ''),
                    "most_appropriate": options[1] == correct_answers.get('most_appropriate', ''),
                    "option_id": "B",
                    "text": options[1]
                }
            ],
            "question_images": question_images,
            "correct_answers": {
                "least_appropriate": "B" if options[1] == correct_answers.get('least_appropriate', '') else "A",
                "most_appropriate": "A" if options[0] == correct_answers.get('most_appropriate', '') else "B"
            }
        }
    except Exception as e:
        logger.error(f"Error generating MCQ with image options: {e}")
        return {"error": "Failed to generate MCQ"}, 500

def generate_custom_content_appro(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 100:
            return {"error": "Number of questions must be between 1 and 100"}, 400

        images_and_questions = []
        for _ in range(number):
            mcq_with_images = generate_mcq_with_image_options(subject, tone)
            if "error" in mcq_with_images:
                return {"error": "Failed to generate MCQ"}, 500

            # Add to results
            images_and_questions.append(mcq_with_images)

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

        result = generate_custom_content_appro(num_questions, subject, tone)
        
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

        result = generate_custom_content_appro(num_questions, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in content generation: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/image/<filename>')
def serve_image(filename):
    """Serve an image from the in-memory storage."""
    if filename in image_store_appro:
        image_data = image_store_appro[filename]
        return send_file(BytesIO(image_data), mimetype='image/png')
    return jsonify({"error": "Image not found"}), 404


if __name__ == '__main__':
    app.run(debug=True)
