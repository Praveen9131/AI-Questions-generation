import os
import json
from flask import Flask, request, jsonify
from langchain.chains import LLMChain, SequentialChain
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

def generate_sequence_quiz(number, subject, tone):
    llm = ChatOpenAI(openai_api_key=KEY, model_name="gpt-4", temperature=0.5)
    
    # Construct the predefined text for the quiz
    TEMPLATE = """
    You are an expert quiz maker. Create {number} sequence-based questions for {subject} students in a {tone} tone. 
    Each question should involve arranging steps in the correct sequence to solve a problem or understand a concept in {subject}.
    Ensure the questions are diverse and cover different aspects of {subject}.
    Format the questions according to the provided JSON structure and output as an array. Do not show any question numbers. 
    Use the following format strictly: 
    [
        {{
            "question": "Arrange the following steps in the correct sequence to achieve a specific outcome.",
            "sequence": ["Step 1", "Step 2", "Step 3", "Step 4"],
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "answers": [1, 2, 3, 4]
        }}
    ]
    """

    TEMPLATE2 = """
    You are an expert English grammarian and writer. Given a sequence quiz for {subject} students, evaluate the complexity of the questions and provide a complete analysis of the quiz. 
    Use at most 50 words for the complexity analysis. If the quiz is not appropriate for the cognitive and analytical abilities of the students, update the questions that need to be changed and adjust the tone to better fit the student abilities.
    Quiz:
    {quiz}
    
    Analysis:
    """

    quiz_generation_prompt = PromptTemplate(
        input_variables=["number", "subject", "tone"],
        template=TEMPLATE
    )

    quiz_chain = LLMChain(llm=llm, prompt=quiz_generation_prompt, output_key="quiz")
    
    quiz_evaluation_prompt = PromptTemplate(
        input_variables=["subject", "quiz"],
        template=TEMPLATE2
    )

    review_chain = LLMChain(llm=llm, prompt=quiz_evaluation_prompt, output_key="review", verbose=True)
    
    generate_evaluate_chain = SequentialChain(
        chains=[quiz_chain, review_chain],
        input_variables=["number", "subject", "tone"],
        output_variables=["quiz", "review"],
        verbose=True,
    )
    
    # Generate the quiz using the chain
    response = generate_evaluate_chain({
        "number": number,
        "subject": subject,
        "tone": tone
    })
    
    # Assume response.get("quiz") is supposed to return a JSON string
    quiz_json = response.get("quiz")
    
    # Print the raw quiz JSON for debugging
    print("Raw quiz JSON:", repr(quiz_json))
    
    # Check if quiz_json is None or empty and ensure it is a valid JSON string
    if not quiz_json:
        return None
    
    try:
        quiz_data = json.loads(quiz_json)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None
    
    return quiz_data
