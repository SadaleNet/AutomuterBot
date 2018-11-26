#!/bin/python3
'''
Copyright 2018 Wong Cho Ching <https://sadale.net>

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

import logging
import sqlite3
import json
import urllib
import urllib.error
import urllib.request
import os

#logging.basicConfig(filename='data/chat.log', format='%(asctime)s:%(levelname)s:%(message)s', level=logging.INFO)
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', level=logging.INFO)
DATA_UPDATE_OFFSET_PATH = 'data/update_offset'
MAX_API_RESPOSE_DELAY = 30
longPollDuration = 300

connection = sqlite3.connect('data/database.sqlite')
c = connection.cursor()
c.execute("CREATE TABLE IF NOT EXISTS user_id_map (username TEXT, userId INTEGER PRIMARY KEY)")
connection.commit()

#Load the telegram update offset from file
telegramOUpdateOffset = 0
if os.path.exists(DATA_UPDATE_OFFSET_PATH):
    try:
        with open(DATA_UPDATE_OFFSET_PATH, 'r', newline=None) as f:
            telegramOUpdateOffset = int(f.read().replace('\n', ''))
    except:
        pass #If we fail to read the file, we give up.


with open('./data/token') as f:
    token = f.readline().replace('\n', '')

def recordUserId(username:str, userId:int):
    c.execute('SELECT COUNT(*) FROM user_id_map WHERE userId = ?', (userId,))
    count, = c.fetchone()
    if count == 0:
        c.execute("INSERT INTO user_id_map (username, userId) VALUES (?, ?)", (username, userId))
    else:
        c.execute("UPDATE user_id_map SET username = ? WHERE userId = ?", (username, userId))

def retrieveUserId(username:str):
    #Telegram username is case-insensitive. That's why the "COLLATE NOCASE"
    c.execute('SELECT userId FROM user_id_map WHERE username = ? COLLATE NOCASE', (username,))
    data = c.fetchone()
    return data[0] if data != None else None


def telegramCallApiInner(apiMethod:str, data:dict, timeout:float):
    return urllib.request.urlopen(
            urllib.request.Request(
                    "https://api.telegram.org/bot{}/{}".format(token, apiMethod),
                    data=urllib.parse.urlencode(data).encode(),
                    method="POST"),
                timeout=timeout
            )

#Call telegram API and return a parsed dict of json.
def telegramCallApi(apiMethod:str, data:dict, timeout:float):
    jsonResponseData = None
    try:
        with telegramCallApiInner(apiMethod, data, timeout) as response:
            responseData = response.read()
            try:
                jsonResponseData = json.loads(responseData.decode('utf-8'))
            except json.JSONDecodeError as jsonError:
                logging.error("Telegram API Server Issue: Responded with invalid JSON payload:"+jsonError.msg+":"+responseData.decode("utf-8"))
    except urllib.error.HTTPError as response:
        logging.error("HTTP Error, did you get disconnected from the internet? Details:"+response.read().decode("utf-8"))
    except Exception as e:
        logging.error("Other Error, did you get disconnected from the internet? Details:"+str(e))
    return jsonResponseData

while True:
    #Perform long-polling
    jsonResponseData = telegramCallApi("getUpdates", {"offset": telegramOUpdateOffset, "timeout":longPollDuration}, longPollDuration+MAX_API_RESPOSE_DELAY)
    logging.info(jsonResponseData)
    #Sanitize the message. Ignore invalid responses
    if jsonResponseData == None:
        continue
    if 'ok' not in jsonResponseData or jsonResponseData['ok'] == False or 'result' not in jsonResponseData:
        continue
    #Parse the result, one-by-one.
    results = jsonResponseData['result']
    for result in results:
        if 'update_id' not in result:
            continue

        if result['update_id']+1 > telegramOUpdateOffset:
            telegramOUpdateOffset = result['update_id']+1
            with open(DATA_UPDATE_OFFSET_PATH, 'w', newline=None) as f:
                f.write(str(telegramOUpdateOffset))
        if 'message' in result:
            message = result['message']
            fromInfoExtracted = False
            chatInfoExtracted = False

            #Extract the info about the guy who sent the message
            if 'from' in message:
                if 'id' in message['from']:
                    fromId = message['from']['id']
                    if 'username' in message['from']:
                        username = message['from']['username']
                        recordUserId(username, fromId)
                    fromInfoExtracted = True
                else:
                    logging.error("Telegram API responded with from without id")

            #Extract the chat ID and chat type
            if 'chat' in message:
                if 'id' in message['chat'] and 'type' in message['chat']:
                    chatId = message['chat']['id']
                    chatType = message['chat']['type']
                    chatInfoExtracted = True
                else:
                    logging.error("Telegram API responded with chat without chat id")

            #Check if someone had sent a command to the bot
            if chatInfoExtracted and fromInfoExtracted and 'text' in message:
                fields = message['text'].split(' ')
                
                command = fields[0]
                #Perform the approval
                if command.startswith('/approve'):
                    #Get a list of admin. And only allows admins to perform the approval
                    response = telegramCallApi("getChatAdministrators", {"chat_id": chatId}, MAX_API_RESPOSE_DELAY)
                    adminUsersId = []
                    if response != None and 'ok' in response and response['ok'] == True and 'result' in response:
                        adminUsersId = [i['user']['id'] for i in response['result']]
                    if fromId in adminUsersId: #check if the user is an admin
                        #Handles @Username
                        users = fields[1:]
                        if len(users) == 0:
                            telegramCallApi("sendMessage", {"chat_id": chatId, "text":"Please specify the user to be unrestriced."}, MAX_API_RESPOSE_DELAY)
                        else:
                            for user in users:
                                if user.startswith('@'):
                                    userId = retrieveUserId(user[1:])
                                    if userId != None:
                                        response = telegramCallApi("restrictChatMember", {"chat_id": chatId, "user_id":userId, "until_date":0, "can_send_messages":True, "can_send_media_messages":True, "can_send_other_messages":True, "can_add_web_page_previews":True}, MAX_API_RESPOSE_DELAY)
                                        if response == None or 'ok' not in response or response['ok'] == False:
                                            telegramCallApi("sendMessage", {"chat_id": chatId, "text":"Approval failed. Have you granted 'Ban Users' priviledge to this bot?"}, MAX_API_RESPOSE_DELAY)
                        #Handles text_mention
                        if 'entities' in message:
                            for entity in message['entities']:
                                if 'type' in entity and entity['type'] == 'text_mention':
                                    if 'user' in entity and 'id' in entity['user']:
                                        userId = entity['user']['id']
                                        telegramCallApi("restrictChatMember", {"chat_id": chatId, "user_id":userId, "until_date":0, "can_send_messages":True, "can_send_media_messages":True, "can_send_other_messages":True, "can_add_web_page_previews":True}, MAX_API_RESPOSE_DELAY)
                                        if response == None or 'ok' not in response or response['ok'] == False:
                                            telegramCallApi("sendMessage", {"chat_id": chatId, "text":"Approval failed. Have you granted 'Ban Users' priviledge to this bot?"}, MAX_API_RESPOSE_DELAY)
                if chatType == 'private':
                    telegramCallApi("sendMessage", {"chat_id": chatId, "text":"Success!\nYour username to user ID mapping is updated. Now you can ask the admin to /approve you.\nIf you want to have this bot to moderate your group, invite it to your supergroup, make it an admin and grant it 'Ban Users' privilege.\nIf you also want it to delete join messages, also grant it 'Delete messages' privilege."}, MAX_API_RESPOSE_DELAY)
            #Check if a new member had joined
            if chatInfoExtracted and 'new_chat_members' in message:
                #Loop thru each new member and mute them
                for newChatMember in message['new_chat_members']:
                    if 'id' in newChatMember:
                        if 'username' in newChatMember:
                            recordUserId(newChatMember['username'], newChatMember['id'])
                        newMemberResponseJson = telegramCallApi("restrictChatMember", {"chat_id": chatId, "user_id":newChatMember['id'], "until_date":0, "can_send_messages":False, "can_send_media_messages":False, "can_send_other_messages":False, "can_add_web_page_previews":False}, MAX_API_RESPOSE_DELAY)
                        if 'message_id' in message:
                            telegramCallApi("deleteMessage", {"chat_id": chatId, "message_id": message['message_id']}, MAX_API_RESPOSE_DELAY)
                        if newMemberResponseJson == None or 'ok' not in newMemberResponseJson and newMemberResponseJson['ok'] == False:
                            telegramCallApi("sendMessage", {"chat_id": chatId, "text":"Failed to restrict the new member. Have you granted 'Ban Users' priviledge to this bot?"}, MAX_API_RESPOSE_DELAY)
                    else:
                        logging.error("Telegram API Server Issue: Responded with new_chat_members without user id")
            connection.commit()
