
# subtitle-generator
A Python app that automatically creates subtitle for any video/audio file as long as a transcript is provided.
The program uses [lowerquality's "gentle" forced aligner](https://github.com/lowerquality/gentle) to retrieve the timings of the words.  
I explained the program and the process of making it in [a video on my YouTube channel:  
![video_thumbnail](https://i.ytimg.com/vi/8yZ-x-WuFw0/hqdefault.jpg?sqp=-oaymwEZCPYBEIoBSFXyq4qpAwsIARUAAIhCGAFwAQ==&rs=AOn4CLB6LOTtrUvG8UDAvOBLi8DAtdOpjA)](https://youtu.be/8yZ-x-WuFw0)


## How to install (only tested on Linux)
1. Clone this repository
2. Clone [gentle](https://github.com/lowerquality/gentle) into a subfolder called "gentle" inside the local repository
3. Run gentle's `install.sh` script (I've had problems with it not installing every dependency automatically, so you may have to try it a few times while installing the missing dependencies using `apt-get install`
4. Paste your desired font at the root of the `subtitle-generator` repository (same folder as `subtitle_generator.py`)
5. Make sure you have `PIL` and [`ffmpeg-python`](https://github.com/kkroening/ffmpeg-python) installed using `pip`

## How to use
1. Edit `subtitle_generator.py`in any IDE/Text editor and changes the UPPERCASE variables at the top (don't forget to set the right font!)
2. Run the `subtitle_generator.py` script with the necessary arguments

## Arguments

 - `--input` The input file (video or audio) for which the subtitles should be generated [Default value: "video.mp4"]
 - `--output`The output file (will be a .mp4 video file) [Default value: "output.mp4"]
 - `--start_frame`The frame at which the program will start to generate subtitles [Default: 0]
 - `--end_frame`The frame at which the program will cease to generate subtitles [Default: last frame]
 - `--framerate`The framerate of the input video (ignore if it's just an audio file) [Default: 60]
 - `--width`and `--height`The dimensions of the input video (ignore if it's just an audio file) [Default: 1920x1080]
 - `--clear_existing`If specified, the program will delete all previously generated frames saved inside the image sequence output directory
 - `--overlay`If specified, the output file will be the input file + the subtitles. If it isn't, the output file will just be the subtitles on a green background, which can then be easily edited on top of the video. This option is not recommended as the video will be unusable if the specified dimensions are wrong (while the green background video offers more flexibility), and currently it seems like audio is lost in the process.
 - `--cache_subtitles`and `load_subtitles`have not yet been implemented.


