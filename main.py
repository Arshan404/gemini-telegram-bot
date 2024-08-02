import os
import re
import aiohttp
import asyncio
import telebot
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BASE_API_URL = os.getenv('BASE_API_URL')
API_KEY = os.getenv('API_KEY')

bot = telebot.TeleBot(TOKEN)

def escape_markdown(text):
    text = text.replace('\\n', '\n')
    markdown_chars = r'[\*_\[\]()~`>#\+\-=|{}\.!]'
    escaped_text = re.sub(markdown_chars, lambda m: '\\' + m.group(0), text)
    return escaped_text

async def handle_api_request(message, delete=False, image_url=None):
    user_id = str(message.from_user.id)
    message_id = str(message.message_id)

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY
    }
    async with aiohttp.ClientSession() as session:
        if delete:
            async with session.delete(f"{BASE_API_URL}/delete/{user_id}", headers=headers) as response:
                return ["Conversation deleted."] if response.status == 200 else ["Error in deletion."]
        else:
            query_text = message.caption if message.content_type == 'photo' else message.text
            if image_url and (query_text == "" or query_text is None):
                query_text = "What insights can you provide about this image?"

            data = {
                "message_id": message_id,
                "query": query_text,
            }
            if image_url:
                data["image"] = True
                data["image_url"] = image_url

            async with session.post(f"{BASE_API_URL}/conversations/{user_id}", headers=headers, json=data) as response:
                if response.status == 200:
                    response_text = []
                    async for line in response.content.iter_any():
                        decoded_line = line.decode('utf-8').strip()
                        if decoded_line:
                            response_text.append(decoded_line)
                    return response_text
                else:
                    return ["Sorry, there was an error processing your request."]

def handle_text(message):
    delete_command = message.text.strip() in ['/delete', '/clear'] if message.text else False
    image_url = None
    if message.content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        image_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"

    with ThreadPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(executor, lambda: asyncio.run(handle_api_request(message, delete=delete_command, image_url=image_url)))
        response_text = future.result()

    full_response_text = ""
    for response in response_text:
        formatted_response = escape_markdown(response)
        full_response_text += formatted_response if full_response_text else formatted_response

    if full_response_text:
        bot.send_chat_action(message.chat.id, 'typing')
        bot.send_message(message.chat.id, full_response_text, parse_mode='MarkdownV2', disable_web_page_preview=True)

@bot.message_handler(content_types=['text', 'photo'])
def on_message(message):
    handle_text(message)

if __name__ == '__main__':
    print("Bot started")
    bot.polling(none_stop=True)
