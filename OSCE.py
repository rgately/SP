from pvrecorder import PvRecorder
import wave
import struct
import os
import openai
import curses
from curses import wrapper
import time
from threading import Thread
from threading import Event
from gtts import gTTS
import json
import random

USE_TTS = True
SPEED = 2.0
CHECK_CORRECTNESS = False

path="test.wav"
key_path = "key.json"
prompt_path = "prompts/prompt_2"
doornote_path = "prompts/prompt_doornote"
diagnosis = "NULL"
CC_diagnosis_list = {"chest pain": ["stable angina", "acute myocardial infarction", "pulmonary embolism", "pneumothorax", "GERD", "Aortic dissection", "pericarditis"], 
"acute cough" : ["sinusitis", "brochitis", "pertussis", "pneumonia", "viral URI", "pulmonary embolism"],
"chronic cough" : ["asthma", "COPD", "post-nasal drip", "GERD", "Smoker's cough", "lung cancer", "bronchiectasis", "medication-induced cough"],
"dyspnea" : ["pneumonia", "COPD", "pulmonary embolism", "congestive heart failure", "malignant pleural effusion", "anemia"]}

cc = random.choice(list(CC_diagnosis_list.keys()))
diagnosis = random.choice(CC_diagnosis_list[cc])
prompt_addon = "Your chief complaint is " + cc + ". Your secret diagnosis is " + diagnosis + "."

with open(key_path) as key_file:
    key_json = json.load(key_file)
    openai.api_key = key_json["key"]

with open(prompt_path) as script_file:
    prompt = script_file.read()
    initial_prompt = prompt + prompt_addon
    #print(initial_prompt)
    #exit(0)
with open(doornote_path) as doornote_file:
    doornote_prompt = doornote_file.read()
    initial_doornote_prompt = doornote_prompt + prompt_addon
    #print(initial_doornote_prompt)

chat_history_doornote = [{"role":"system", "content" : initial_doornote_prompt}]
door_note = openai.ChatCompletion.create(model="gpt-4", messages=chat_history_doornote)["choices"][0]["message"]["content"]
print(door_note)

#exit(0)

event = Event()
def record() :
        recorder = PvRecorder(device_index=-1, frame_length=512)
        audio = []
        recorder.start()

        while True:
                frame = recorder.read()
                audio.extend(frame)
                if event.is_set() :
                        recorder.stop()
                        with wave.open(path, 'w') as f:
                                f.setparams((1, 2, 16000, 512, "NONE", "NONE"))
                                f.writeframes(struct.pack("h" * len(audio), *audio))
                        recorder.delete()
                        break

def main(stdscr):
    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)

    instruction_pos = 5

    stdscr.clear()
    stdscr.addstr(1,0, str(door_note + "\n\nPress spacebar to continue..."), curses.color_pair(2))
    stdscr.refresh()
    stdscr.getch()
    stdscr.clear()

    lines = initial_prompt.splitlines()
    chat_history = []
    for message in lines :
        chat_history.append({"role":"system", "content" : message})

    total_transcript = ""
    selective_transcript = ""

    while True:
        user_input = ""
        # Clear screen y,x
        #stdscr.clear()
        stdscr.addstr(instruction_pos,0,"Press any key to start recording...", curses.color_pair(1))
        stdscr.refresh()
        stdscr.getch()
        while True:
            record_thread = Thread(target = record)
            record_thread.start()

            #stdscr.clear()
            stdscr.addstr(instruction_pos,0,"Listening... Press any key to stop.", curses.color_pair(1))
            stdscr.refresh()

            stdscr.getch()
            event.set()
            record_thread.join()
            event.clear()
            audio_file= open(path, "rb")
            transcribed_audio = openai.Audio.transcribe("whisper-1", audio_file)
            if not CHECK_CORRECTNESS :
                user_input = transcribed_audio["text"] 
                break
            #stdscr.clear()
            stdscr.addstr(instruction_pos,0,"I thought I heard: " + "\"" + transcribed_audio["text"] + "\", is that correct? (y/n) : ", curses.color_pair(1))
            stdscr.refresh()
            key = stdscr.getch()
            if key != ord("n"):
                user_input = transcribed_audio["text"] 
                break


        if "quit the interview" in user_input.lower().rstrip() :
            break
        else :
            selective_transcript += ("MEDICAL STUDENT: " + "\"" + user_input + "\"" + "\n")
            total_transcript += ("MEDICAL STUDENT: " + "\"" + user_input + "\"" + "\n")
            chat_history.append({"role":"user", "content" : user_input})
            response = openai.ChatCompletion.create(model="gpt-4", messages=chat_history)
            stdscr.clear()
            stdscr.addstr(1,0, ">" + response["choices"][0]["message"]["content"].strip("\n"), curses.color_pair(2))
            stdscr.refresh()
            if USE_TTS:
                myobj = gTTS(text=response["choices"][0]["message"]["content"].strip("\n"), lang="en", slow=False)
                myobj.save("response.mp3")
                os.system("mpg123 -q -d 2 response.mp3")

            chat_history.append({"role":"assistant", "content" : response["choices"][0]["message"]["content"].strip("\n")})
            total_transcript += ("PATIENT: " + "\"" + response["choices"][0]["message"]["content"].strip("\n") + "\"" + "\n")
    

    # curses.endwin()
    # checklist = """
    # 1) Addresses the patient by name
    # 2) Introduces self by name AND title
    # 3) Involves patient when discussing the reason for their visit
    # 4) Maintains appropriate eye contact
    # 5) Uses effective body language
    # 6) Legitimizes patient’s emotions
    # 7) Reinforces positive behaviors
    # 8) Encourages questions or concerns
    # 9) Elicits patient perspective
    # 10) Avoids interrupting patient
    # 11) Avoids leading questions
    # 12) Avoids multiple questions
    # 13) Conducts the interactions in an organized manner
    # 14) Uses open- and close-ended questions effectively
    # 15) Checks for accuracy during the interview
    # 16) Summarizes the interview (history and exam, if applicable)
    # 17) Avoids inappropriate language
    # 18) Reviews next steps
    # 19) Verifies patient’s understanding
    # """
    # print(selective_transcript)
    # chat_history = [{"role":"system", "content" : "You are tasked with evaluating a medical student's conduct. You will be given a transcript containing quotes from a medical student."}]
    # chat_history.append({"role":"system", "content" : "You are to use the following checklist to evaluate the medical student's performance:"})
    # chat_history.append({"role":"system", "content" : checklist})
    # chat_history.append({"role":"system", "content" : "This is the transcript:"})
    # chat_history.append({"role":"system", "content" : selective_transcript})
    # chat_history.append({"role":"system", "content" : "Mark a YES next to each item on the checklist if the medical student displayed the listed behavior and provide an example quote (if applicable) from the transcript to support this. Show the checklist when you are done."})

    # response = openai.ChatCompletion.create(model="gpt-4", messages=chat_history)
    
    # with open("response.txt", "w") as file:
    #     file.write(total_transcript)
    #     file.write("\n\n\n")
    #     file.write(response["choices"][0]["message"]["content"])
    #     file.write("\n\nTotal tokens: " + str(response['usage']['total_tokens']))


if __name__ == "__main__" :
    try:
        wrapper(main)
    except KeyboardInterrupt:
        print("The diagnosis was " + diagnosis)
# wrapper(main)

#print(str("The diagnosis was " + diagnosis))
