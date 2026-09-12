import json
from discord import Member

def member_to_json(json_dict):
    def lookForMember(jsonDict):
        org_dict = jsonDict.copy()
        for key, value in org_dict.items():
            if type(value) == dict:
                jsonDict[key] = lookForMember(value)
            if type(key) == Member:
                res = jsonDict.pop(key)
                key = f"<MemberID={key.id}>"
                jsonDict[key] = res
            elif type(value) == Member:
                jsonDict[key] = f"<MemberID={value.id}>"
        return jsonDict
    return lookForMember(json_dict)

class MemberJsonDecoder(json.JSONDecoder):
    def __init__(self, guild, *args, **kwargs):
        self.guild = guild
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, json_dict):
        def lookForMember(jsonDict):
            org_dict = jsonDict.copy()
            for key, value in org_dict.items():
                if type(value) == dict:
                    jsonDict[key] = lookForMember(value)
                if str(key).startswith("<MemberID="):
                    res = jsonDict.pop(key)
                    member_id = int(key.strip("<>").split("=")[1])
                    member = self.guild.get_member(member_id) if self.guild else member_id
                    jsonDict[member] = res
                elif str(value).startswith("<MemberID="):
                    member_id = int(str(value).strip("<>").split("=")[1])
                    jsonDict[key] = self.guild.get_member(member_id) if self.guild else member_id
            return jsonDict
        return lookForMember(json_dict)
