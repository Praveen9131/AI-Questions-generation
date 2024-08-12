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

def generate_fill_in_the_blank(subject: str, tone: str):
    """Generate a fill-in-the-blank question with corresponding answers."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a fill-in-the-blank question with corresponding answers based on the subject '{subject}'. The question should have multiple blanks and provide the correct answers as a comma-separated list. Use the following format:\n\n**Question:** [Question with blanks represented by '_______']\n\n**Answers:** [Comma-separated correct answers]\n\nEnsure that the question is clear and understandable."}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=description_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        content = response.choices[0].message.content

        question_section = content.split("**Question:**")[1].split("**Answers:**")[0].strip()
        answers_section = content.split("**Answers:**")[1].strip()

        return {
            "question": question_section,
            "answer": answers_section
        }
    except Exception as e:
        logger.error(f"Error generating fill-in-the-blank question: {e}")
        return {"error": "Failed to generate fill-in-the-blank question"}

def generate_quiz1(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 10:  # Ensure number is within allowed range
            return {"error": "Number of questions must be between 1 and 10"}, 400

        questions = []
        for _ in range(number):
            question = generate_fill_in_the_blank(subject, tone)
            if "error" in question:
                return {"error": "Failed to generate fill-in-the-blank question"}, 500
            questions.append(question)

        return questions
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

        result = generate_quiz1(num_questions, subject, tone)
        
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

        questions = generate_quiz1(num_questions, subject, tone)
        if isinstance(questions, tuple) and len(questions) == 2 and isinstance(questions[0], dict) and 'error' in questions[0]:
            return jsonify(questions[0]), questions[1]

        return jsonify(questions)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500

