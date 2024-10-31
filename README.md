# System Captioner

Generates and shows real-time captions by listening to your Windows PC's audio. Makes digital content more accessible for those who are deaf or hard of hearing, aids language learning, and more. 


https://github.com/user-attachments/assets/7315ab7c-fe30-4c37-91aa-60bb32979338


## How it works

1. Captures system audio in real-time through Windows audio loopback using PyAudioWPatch
3. Locally transcribes the recordings using faster-whisper
4. Displays the transcriptions as captions in a overlay window that remains always on top


Language auto-detection, user-friendly GUI, draggable captions box, and intelligent mode that shows captions only when speech is detected.

By default, the app runs on and requires nVidia CUDA. As it is, the app should work with RTX 2000, 3000 and 4000 series cards.   

Turning off GPU mode will make the app run on CPU; start with the smallest model and settle with the model that's stable. 

## Installation (Windows)

**Method 1 (fastest):**

1. Download the latest standalone .zip (currently 1.37) from the releases section and extract all files. 
 
2. Run SystemCaptioner.exe an follow the instructions.

Alternatively build the standalone executable yourself using build_portably.py

## Troubleshooting 

If you have any issues, send them to me via the 'Issues' section at the top of this page. Include the Console window log if possible. 
