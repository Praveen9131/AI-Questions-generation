import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

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

def generate_mcq(subject: str, tone: str):
    """Generate a multiple-choice question (MCQ) with four text options."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a clear and understandable question with exactly four options based on the subject '{subject}'. The question should have exactly one correct answer. Each option should be related to the concept in the subject and in a '{tone}' tone. Use the following format:\n\n**Question:** [Question based on the subject]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n3. [Option 3]\n4. [Option 4]\n\n**Correct Answer:** [Correct Option by number]\n\nEnsure that all four options are provided and exactly one correct answer."}
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
        options_section = content.split("**Options:**")[1].split("**Correct Answer:**")[0].strip()
        correct_answer_section = content.split("**Correct Answer:**")[1].strip()

        options_list = options_section.split('\n')
        options_dict = {
            f"option{i+1}": option.split('. ', 1)[-1].strip()  # Remove leading "1. ", "2. ", etc.
            for i, option in enumerate(options_list)
        }

        # Extract the correct answer number, assuming it's formatted like "2. ..."
        correct_answer_number = correct_answer_section.split('.')[0].strip()
        correct_answer_index = int(correct_answer_number)
        correct_answer_mapped = [f"option{correct_answer_index}"]

        return {
            "question": question_section,
            "options": options_dict,
            "correct_answers": correct_answer_mapped
        }
    except Exception as e:
        logger.error(f"Error generating MCQ: {e}")
        return {"error": "Failed to generate MCQ"}

def generate_quiz(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 10:  # Ensure number is within allowed range
            return {"error": "Number of questions must be between 1 and 10"}, 400

        mcqs = []
        for _ in range(number):
            mcq = generate_mcq(subject, tone)
            if "error" in mcq:
                return {"error": "Failed to generate MCQ"}, 500
            mcqs.append(mcq)

        return mcqs
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

        result = generate_quiz(num_questions, subject, tone)
        
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

        mcqs = generate_quiz(num_questions, subject, tone)
        if isinstance(mcqs, tuple) and len(mcqs) == 2 and isinstance(mcqs[0], dict) and 'error' in mcqs[0]:
            return jsonify(mcqs[0]), mcqs[1]

        return jsonify(mcqs)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500


