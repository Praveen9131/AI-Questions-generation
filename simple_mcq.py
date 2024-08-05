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
def generate_quiz(number, subject, tone):
    llm = ChatOpenAI(openai_api_key=KEY, model_name="gpt-4", temperature=0.5)
    
    # Construct the predefined text for the quiz
    predefined_text = f"Based on the fundamentals of {subject}, create a quiz that encompasses the core concepts and challenges students' understanding."
    RESPONSE_JSON = {
    "": {
        "mcq": "multiple choice question",
        "options": {
            "a": "choice here",
            "b": "choice here",
            "c": "choice here",
            "d": "choice here",
        },
        "correct": "correct answer",
    },
    "": { 
        "mcq": "multiple choice question",
        "options": {
            "a": "choice here",
            "b": "choice here",
            "c": "choice here",
            "d": "choice here",
        },
        "correct": "correct answer",
    },
    "": {
        "mcq": "multiple choice question",
        "options": {
            "a": "choice here",
            "b": "choice here",
            "c": "choice here",
            "d": "choice here",
        },
        "correct": "correct answer",
    },
}
   # Construct the template without using RESPONSE_JSON directly unless it's a variable you pass to LLMChain
    TEMPLATE = f"""
    Text: {predefined_text}
    You are an expert MCQ maker. Given the above text, it is your job to \
    create a quiz  of {number} multiple choice questions for {subject} students in {tone} tone. 
    Make sure the questions are not repeated and check all the questions to be conforming the text as well.
    Make sure to format your response like  RESPONSE_JSON below  and use it as a guide. \
    Ensure to make {number} MCQs in th forrmate of above variable 
      ,please give me in this format RESPONSE_JSON format of arrayand use the keywords only question,options ,answershow me first question then options then answer
      dont generate question numbers 
      [{
          "question"
          "options""show the 4 options in the format od a,b,c,d"
          "answer" 
      }]use only this format dont use any other format
       
           
         follow only this format
            // More questions as needed...
      
    """
    TEMPLATE2="""
    You are an expert english grammarian and writer. Given a Multiple Choice Quiz for {subject} students.\
    You need to evaluate the complexity of the question and give a 
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    +complete analysis of the quiz. Only use at max 50 words for complexity analysis. 
    if the quiz is not at per with the cognitive and analytical abilities of the students,\
    update the quiz questions which needs to be changed and change the tone such that it perfectly fits the student abilities
    Quiz_MCQs:
    {quiz}
    
    Check from an expert English Writer of the above quiz:
    """

    quiz_generation_prompt = PromptTemplate(
        input_variables=[ "number", "subject", "tone", "response_json"],
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
        "response_json": json.dumps(RESPONSE_JSON)
    })
    #quiz=response.get("quiz")
# Assume response.get("quiz") is supposed to return a JSON string
    quiz_json = response.get("quiz")
    quiz_data = json.loads(quiz_json)

# Check if quiz_json is None or empty and ensure it is a valid JSON string
    return quiz_data




