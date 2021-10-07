# Bot_Beta_Single-Server

This is a bot for a discord server of a friend where we play werewolf. It's assisting the gamemaster to manage the game better.
It is open source and written in Python. 

No guarantee this bot works as it should.

The only language supported is currently german.

LG the developer [@StrableD](https://www.github.com/StrableD)

# Usage

You need to create a new database file in `/data/db/` naming it `database.db`. You can change the values in the database with tools like DB Browser (SQLite).
For the password of your database and the token of your bot you need another file in `/data/` named `auth.0` containing a json object with your token and your password.
```json
{
  "token":"your-token",
  "password": "your-password"
}
```
