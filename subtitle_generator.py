from PIL import Image, ImageDraw, ImageFont
from math import *
from subprocess import Popen, PIPE

import os
import ffmpeg
import logging
import argparse
import json

FONT = ImageFont.truetype('Comfortaa-Bold.ttf', 75)

OUTLINE_SIZE = 6
SUBTITLE_HEIGHT = 140
MAX_SUBTITLE_DURATION = 3
MAX_WORD_DURATION = 0.6
MAX_SUBTITLE_WIDTH = 1800

OUTLINE_COLOR = (0, 0, 0, 255)
TEXT_COLOR = (255, 255, 255, 255)
BACKGROUND_COLOR = (0, 255, 0) # Will be removed when --overlay is present

IMAGE_SEQUENCE_OUTPUT_DIRECTORY = "generated_image_sequence"

logging.getLogger().setLevel("DEBUG")


parser = argparse.ArgumentParser(description='Generate subtitles for a video based on a transcript.')

parser.add_argument('--input', default="video.mp4", type=str, help='the input file (audio or video)')
parser.add_argument('--transcript', default="transcript.txt", type=str, help='the transcript file (.txt)')
parser.add_argument('--output', default="output.mp4", type=str, help='the video output file')
parser.add_argument('--start_frame', default=0, type=int, help='the first frame (starting at 0) of the video from which the subtitles will be generated')
parser.add_argument('--end_frame', default=-1, type=int, help='the last frame (starting at 0) of the video to which the subtitles will be generated')
parser.add_argument('--framerate', default=60, type=int, help="the framerate of the input video")
parser.add_argument("--width", default=1920, type=int, help="The width of the input video")
parser.add_argument("--height", default=1080, type=int, help="The height of the input video")
parser.add_argument("--clear_existing", help="clear existing frames if exist", action="store_true")
parser.add_argument("--overlay", help="overlay the generated subtitles onto the input video (will create a new video and not overwrite the input file)", action="store_true")
parser.add_argument("--cache_subtitles", help="if this is enabled, the aligned subtitles will be saved along with their times in a file called 'subtitles.txt'", action="store_true")
parser.add_argument("--load_subtitles", help="load cached subtitles instead of re-aligned them.", action="store_true")

args = parser.parse_args()

# If we want to overlay the subtitles on top of the input video, the base has to be fully transparent
if args.overlay:
    base = Image.new('RGBA', (args.width, args.height), (0,0,0,0))
else:
    base = Image.new('RGB', (args.width, args.height), BACKGROUND_COLOR)

if os.path.exists(IMAGE_SEQUENCE_OUTPUT_DIRECTORY):
    if (args.clear_existing):
        logging.info("Image sequence output directory already exists. Clearing...")
        for filename in os.listdir(IMAGE_SEQUENCE_OUTPUT_DIRECTORY):
            os.remove(os.path.join(IMAGE_SEQUENCE_OUTPUT_DIRECTORY, filename))
else:
    os.makedirs(IMAGE_SEQUENCE_OUTPUT_DIRECTORY)

def generate_text_image(text, scale=1):
    txt_size = FONT.getsize(text)
    txt_img = Image.new('RGBA', (txt_size[0]+OUTLINE_SIZE*2, txt_size[1]+OUTLINE_SIZE*2), (0,0,0,0) if args.overlay else BACKGROUND_COLOR)

    draw = ImageDraw.Draw(txt_img)

    # Draw outline
    for i in range(100):
        angle = i/100*(2*pi)
        draw.text((OUTLINE_SIZE+sin(angle)*OUTLINE_SIZE, OUTLINE_SIZE+cos(angle)*OUTLINE_SIZE), text, font = FONT, fill = OUTLINE_COLOR)

    # Draw text itself
    draw.text((OUTLINE_SIZE, OUTLINE_SIZE), text, font = FONT, fill = TEXT_COLOR)

    if scale == 1:
        return txt_img
    else:
        txt_img = txt_img.resize((floor(txt_img.size[0]*scale), floor(txt_img.size[1]*scale)), Image.ANTIALIAS)
        return txt_img

# Used to create the bounce animation
def get_text_scale_at_frame(start_time, frame):
    frame_time = frame/args.framerate
    x = frame_time - start_time
    scale = -(x*7-1)**2+1.1 # Upside-down parabola
    if x > 0.2:
        scale = max(scale, 1)
    
    return scale

# Returns the index of the subtitle that should be shown at the specified frame
def get_subtitle_at_frame(subtitles, times, frame):
    frame_time = frame/args.framerate
    for i in range(len(subtitles)):
        if times[i] <= frame_time and (i>=len(times)-1 or times[i+1] > frame_time):
            return i

# Helper method to lower a string and remove punctuation
def normalize_word(word_str):
    normalized = ""
    for c in word_str.lower():
        if c.isalpha():
            normalized += c

    return normalized

def find_word_in_transcript(aligned_json, word_index):
    transcript_words = aligned_json["transcript"].replace("-", " ").split()
    word_str = normalize_word(aligned_json["words"][word_index]["word"])

    if normalize_word(transcript_words[word_index]) == word_str:
        # Word is at same index in transcript
        return transcript_words[word_index]
    else:
        # Do a manual search
        for i in range(len(transcript_words)):
            if normalize_word(transcript_words[i]) == word_str:
                # Check words around it to see if they match as well
                match = True
                for j in range(-3, 3):
                    if word_index+j > 0 and word_index+j < len(aligned_json["words"]) and normalize_word(transcript_words[i+j]) != normalize_word(aligned_json["words"][word_index+j]["word"]):
                        match = False
                        break

                if match:
                    return transcript_words[i]
        

subtitles = []
times = []

# Call gentle and parse the output JSON
logging.info("Aligning audio using gentle...")
process = Popen(["python3", "gentle/align.py", args.input, args.transcript, "--log", "CRITICAL"], stdout=PIPE)
(proc_output, proc_err) = process.communicate()
process.wait()
# TODO Check if the alignment actually succeeded

aligned_json = json.loads(proc_output)
aligned_words = aligned_json["words"]

# Group the individual words into lines
line = None
line_time = None
logging.info("Creating subtitles...")
for word_index in range(len(aligned_words)):
    word = aligned_words[word_index]

    if word["case"] == "not-found-in-transcript":
        continue
    elif word["case"] == "not-found-in-audio":
        if word_index < 1 or not 'start' in aligned_words[word_index-1]:
            continue
        else:
            word["start"] = aligned_words[word_index-1]["start"]

    if line is None:
        line_time = word["start"]
        line = word["word"]
    else:
        string_to_add = " " + word["word"]

        # If adding the word would make the line bigger then the allowed width, or simply if the word is at the start of a new sentence, add the line to list of subtitles and start again
        if word_index > 1 and (FONT.getsize(line+string_to_add)[0] >= MAX_SUBTITLE_WIDTH or ('start' in aligned_words[word_index-1] and word["start"]-aligned_words[word_index-1]["start"] > MAX_WORD_DURATION)):
            subtitles.append(line)
            times.append(line_time)

            transcript_word = find_word_in_transcript(aligned_json, word_index)
            if transcript_word is not None:
                line = transcript_word
            else:
                line = word["word"]

            line_time = word["start"]
        else: # If it fits, add it to the line
            transcript_word = find_word_in_transcript(aligned_json, word_index)
            if transcript_word is not None:
                line += " " + transcript_word
            else:
                line += " " + word["word"]

# Finally, add the last line to the subtitles
subtitles.append(line)
times.append(line_time)

logging.debug(subtitles)
logging.debug(times)

if times[0] is None:
    t0_in = input("Failed to align first word. Please enter the time of the first word (in seconds): ")
    times[0] = float(t0_in)

# Save all subtitles as an image sequence
frame_count = floor((times[-1]+MAX_SUBTITLE_DURATION)*args.framerate)

# Clamp Start/end frame args
start_frame = min(frame_count, max(0, args.start_frame))

if args.end_frame < 0:
    end_frame = frame_count-1
else: 
    end_frame = min(frame_count, max(start_frame, args.end_frame))

for frame in range(start_frame, end_frame+1):
    subtitle_index = get_subtitle_at_frame(subtitles, times, frame)

    img = base.copy()
    if subtitle_index is not None:
        subtitle = subtitles[subtitle_index]
        start_time = times[subtitle_index]
        txt_img = generate_text_image(subtitle, scale=get_text_scale_at_frame(start_time, frame))
        img.paste(txt_img, (floor(base.size[0]/2-txt_img.size[0]/2), floor(args.height-SUBTITLE_HEIGHT-txt_img.size[1]/2)))

    if args.overlay: # If we want to overlay, we need to save the frames as PNG because we need the Alpha channel.
        img.save(os.path.join(IMAGE_SEQUENCE_OUTPUT_DIRECTORY, "frame_"+str(frame)+".png"), "PNG")
    else: # If not, use JPEG, which takes way less space
        img.save(os.path.join(IMAGE_SEQUENCE_OUTPUT_DIRECTORY, "frame_"+str(frame)+".jpg"), "JPEG")
    logging.info("Saved frame "+str(frame)+"/"+str(end_frame))

# Convert the image sequence into a video using FFMPEG
if args.overlay:
    ffmpeg.input(args.input).overlay(ffmpeg.input(IMAGE_SEQUENCE_OUTPUT_DIRECTORY+'/frame_%d.png', framerate = args.framerate)).output(args.output).run()
else:
    ffmpeg.input(IMAGE_SEQUENCE_OUTPUT_DIRECTORY+'/frame_%d.jpg', start_number = start_frame, framerate = args.framerate).output(args.output).run()