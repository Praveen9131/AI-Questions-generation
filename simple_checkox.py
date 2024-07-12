import os
import json
from flask import Flask, request, jsonify
from langchain.chains import LLMChain
from langchain.chains import SequentialChain
from dotenv import load_dotenv
from langchain_community.callbacks import get_openai_callback
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
KEY = os.getenv("OPENAI_API_KEY")
def generate_quizc(number, subject, tone):
    llm = ChatOpenAI(openai_api_key=KEY, model_name="gpt-4", temperature=0.5)
    
    # Construct the predefined text for the quiz
    
    RESPONSE_JSON = {
    "questions": [
        {
            "statement": "Question statement here",
            "options": [
                "[].Option 1",
                "[].Option 2",
                "[].Option 3",
                "[].Option 4" "generate the []symbol for each option"
            ],
            "correct": ["Option 1", "Option 3"]  # List all correct options
        }
        # More questions as needed...
    ]
}
   # Construct the template without using RESPONSE_JSON directly unless it's a variable you pass to LLMChain
    TEMPLATE = f"""
    
    You are an expert checkbox maker. Create {number} checkbox-type questions for {subject} students in a {tone} tone. 
    Each question should have multiple statements where more than one can be true. Ensure the questions are diverse and cover different aspects of {subject}.
    Format the questions according to the provided JSON structure give me the output in arrayand dont show any question numbersplease give me in this format RESPONSE_JSON format of arrayand use the keywords only question,options ,answershow me first question then options then answer
      dont generate question numbers 
      [{
          "question"
          "options""show the 4 options in the format of a,b,c,d should be there"
          "answer" 
      }]use only this format dont use any other format
       
           
         follow only this format
            // More questions as needed...
       
    """
    TEMPLATE2="""
    You are an expert english grammarian and writer. Given a checkbox Quiz for {subject} students.\
    You need to evaluate the complexity of the question and give a complete analysis of the quiz. Only use at max 50 words for complexity analysis. 
    if the quiz is not at per with the cognitive and analytical abilities of the students,\
    update the quiz questions which needs to be changed and change the tone such that it perfectly fits the student abilities
    Quiz_checkbox:
    {quiz}
    
    Check from an expert English Writer of the above quiz:
    """

    quiz_generation_prompt = PromptTemplate(
        input_variables=[ "number", "subject", "tone" ,"response_json"],
        template=TEMPLATE
    )

    quiz_chain = LLMChain(llm=llm, prompt=quiz_generation_prompt, output_key="quiz")
    
    quiz_evaluation_prompt=PromptTemplate(input_variables=["subject", "quiz"], template=TEMPLATE)
    review_chain=LLMChain(llm=llm, prompt=quiz_evaluation_prompt, output_key="review", verbose=True)
    generate_evaluate_chain=SequentialChain(chains=[quiz_chain, review_chain], input_variables=[ "number", "subject", "tone","response_json" ],
                                        output_variables=["quiz", "review"], verbose=True,)
    # Generate the quiz using the chain
    response = generate_evaluate_chain({
        
        "number": number,
        "subject": subject,
        "tone": tone,
        
        "response_json": json.dumps(RESPONSE_JSON),
        
    })
    #quiz=response.get("quiz")
# Assume response.get("quiz") is supposed to return a JSON string
    quiz_json = response.get("quiz")
    quiz_data = json.loads(quiz_json)

# Check if quiz_json is None or empty and ensure it is a valid JSON string
    return quiz_data

