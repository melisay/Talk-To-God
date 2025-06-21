# Talk-To-God: The AI Voice Assistant That Thinks It's Divine

Welcome to the only voice assistant that will sass you, judge you, and maybe answer your questions. Powered by ChatGPT and ElevenLabs, this project lets you talk to a simulated deity with a cosmic sense of humor. Works on Raspberry Pi or over the phone with Twilio. Prepare for short, sarcastic, and occasionally useful responses.

## What Does This Thing Do?

Imagine if your smart speaker had a personality disorder and a direct line to the universe. You get two personalities: Nikki (brutally honest, sharp, and sassy) and Major Tom (cosmic, dramatic, and never boring). Both are ready to roast you, tell you a joke, or drop a fact so random you'll question reality.

## How To Summon The AI God

First, you need Python 3, git, and some API keys. If you don't have those, ask your favorite search engine. Or your actual god.

1. Clone this repository. You know the drill.
2. Make a virtual environment. It's like a safe space for code.
3. Install the requirements:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Copy .env.example to .env and fill in your secrets. If you commit your API keys, the AI God will judge you.

## Example .env File

OPENAI_API_KEY=your_openai_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
TWILIO_ACCOUNT_SID=your_twilio_sid_here
TWILIO_AUTH_TOKEN=your_twilio_token_here
TWILIO_PHONE_NUMBER=your_twilio_number_here
PORT=5001
HOST=0.0.0.0

## Running Locally (Raspberry Pi or Not)

Plug in a microphone and speakers. Run local.py. Speech-to-text uses Google for now. If you want offline speech-to-text, you'll have to add it yourself or wait for a future update.

## Using Twilio (Phone a Deity)

Set up your Twilio account. Point your webhook to /voice. Run twilio_server.py. Use ngrok if you don't have a public server. Call your number and prepare for divine sarcasm.

## Personalities Explained

Nikki: Direct, witty, and never afraid to speak her mind. Short, sharp, and sassy.

Major Tom: Cosmic, philosophical, and always ready with a dramatic one-liner. Never boring.

All responses are short. All responses are funny. If you want long, boring answers, try a different project.

## Entertainment On Demand

Say things like "tell me a joke" or "tell me a riddle" or "tell me a story" or "tell me a fact." The AI God will deliver, with attitude.

## Project Structure (In Human Words)

local.py is for local interaction. twilio_server.py is for phone calls. Personalities and entertainment logic live in their own files. MP3s are cached so you don't have to wait for the same joke twice. .env is where your secrets go. Don't share it. Seriously.

## Important Notes

Keep your .env file secret. If you leak your API keys, the AI God will not help you. Don't commit your virtual environment. That's what .gitignore is for.

## Troubleshooting (Or, Why Isn't This Working?)

If your mic isn't working, check your audio input. If you hear nothing, try installing mpg123 or use a different player. If Twilio ghosts you, check your webhook and ngrok tunnel. If you see "Invalid Key," your .env file is probably wrong. The AI God is not responsible for user error.

## Want To Contribute?

Fork, branch, and make a pull request. Don't break the personalities. Don't rename things for fun. The AI God likes order.

## License

MIT. Because even divine code should be free.


