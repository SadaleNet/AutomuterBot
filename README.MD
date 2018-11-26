# Automuter Telegram Bot

This is a telegram bot that automatically restricts new users from sending anything to the supergroup. `Ban Users` permission has to be granted.

In addition, it's capable for removing join-messages if the `Delete Messages` permission is granted to the bot.

The restriction has to be lift manually by using either `Manage Group` > `Restricted Users`  or by saying `/approve @username1 @username2 @username...`. Any of these actions have to be performed by a supergroup admin.

## Using the Bot
1. Invite the Telegram bot [@AutomuterBot](https://t.me/AutomuterBot) to your supergroup
2. Make it admin and grant it "Ban Users" permission
3. If you would like it to remove join messages, also grant it "Delete Messages" permission

## @username Resolving Issue

There's no telegram API for resolving @username to user ID. For the purpose of restricting the user and removing the restriction, a user ID would be required.

For this reason, we keep a local database of @username to user ID mapping. But there's a problem. If the user changes his username, the local database would be desynchronized from the server. Therefore, the @username_new wouldn't resolve to the user ID with the local database. In this case, `/approve` won't work. Here're two workarounds:

1. Use `Manage Group` > `Restricted Users` in Telegram to remove the restriction
2. Get the restricted user to PM the bot by sending any message. This would synchronize the local database and `/approve` would work again.

## Hosting the Bot

1. Install Python 3. There's no library dependencies other than the standard library.
2. Clone this repo
3. Create the directory `data` inside the cloned repo
4. Create the file `data/token`
5. Create a new Telegram Bot with [@BotFather](https://telegram.me/BotFather). Copy the API token.
6. Put in your API token inside the first line of the content of `data/token`
7. Run automuter.py with Python 3

## Special Thanks

This project was kindly sponsored by **mpower343**
