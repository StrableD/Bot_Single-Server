from lib.bot import bot
import lib.db.db as db

bot.setup()

print(db.saveCurrentGame({312644293602836482:{"sad":"sas"}}, "dorf"))
#evalu = db.setGameToEvaluated(10)
#print(evalu)
print(db.getUnevaluatedGames())
#print(db.getGameToEvaluate(int(input())))
#db.setPlayerElo(312644293602836482, 1300)