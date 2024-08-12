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

def generate_sequence_question(subject: str, tone: str):
    """Generate a sequence arrangement question."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": f"Generate a sequence arrangement question based on the subject '{subject}'. Provide a list of steps in random order and the correct sequence as a list of numbers. Use the following format:\n\n**Question:** [Question asking to arrange the steps in the correct order]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n3. [Option 3]\n4. [Option 4]\n5. [Option 5]\n\n**Correct Sequence:** [Correct order by numbers]\n\n**Correct Order:** [Correct order as a list of steps]\n\nEnsure that all steps are related to the subject and are necessary for the process described."}
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
        options_section = content.split("**Options:**")[1].split("**Correct Sequence:**")[0].strip()
        correct_sequence_section = content.split("**Correct Sequence:**")[1].split("**Correct Order:**")[0].strip()
        correct_order_section = content.split("**Correct Order:**")[1].strip()

        options_list = options_section.split('\n')
        if len(options_list) != 5:
            raise ValueError("Expected exactly 5 options, but found a different number.")

        options_dict = {
            f"option{i+1}": option.split('. ', 1)[-1].strip()  # Remove leading "1. ", "2. ", etc.
            for i, option in enumerate(options_list)
        }
        correct_sequence_list = [int(num.strip()) for num in correct_sequence_section.split(',')]
        correct_order_list = [step.strip() for step in correct_order_section.split('\n')]

        return {
            "question": question_section,
            "options": list(options_dict.values()),  # Convert options_dict to a list
            "answers": correct_sequence_list,
            "sequence": correct_order_list
        }
    except Exception as e:
        logger.error(f"Error generating sequence question: {e}")
        return {"error": "Failed to generate sequence question"}

def generate_sequence_quiz(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 10:  # Ensure number is within allowed range
            return {"error": "Number of questions must be between 1 and 10"}, 400

        questions = []
        for _ in range(number):
            question = generate_sequence_question(subject, tone)
            if "error" in question:
                return {"error": "Failed to generate sequence question"}, 500
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

        result = generate_sequence_quiz(num_questions, subject, tone)
        
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

        questions = generate_sequence_quiz(num_questions, subject, tone)
        if isinstance(questions, tuple) and len(questions) == 2 and isinstance(questions[0], dict) and 'error' in questions[0]:
            return jsonify(questions[0]), questions[1]

        return jsonify(questions)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500


