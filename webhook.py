import requests, re, json
from dateutil.parser import parse
from datetime import datetime, timedelta
import xml.etree.ElementTree as ElementTree




def reverse_bit(num):
    result = 0
    while num:
        result = (result << 1) + (num & 1)
        num >>= 1
    return result


config = json.load(open("config.json"))

session = requests.Session()


hidden_value_reg = r'type\="hidden" name\="(.+?(?="))" value="(.+?(?="))"'
view_state_reg = r'id="javax\.faces\.ViewState" value="(.+?(?="))"'
desc_reg = r'<(label|span) (for|id)="(.+?(?="))">(.+?(?=<))<\/(label|span)>'

h = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate'
}


url = 'https://ges-cas.kordis.fr/login?service=https://myges.fr/j_spring_cas_security_check'
calendar_url = 'https://myges.fr/student/planning-calendar'
home_page = 'https://myges.fr/student/home'
login_url = 'https://ges-cas.kordis.fr/login'

login_page = session.get(url).text

data = dict(re.findall(hidden_value_reg,login_page))

data["username"] = config["username"]
data["password"] = config["password"]
data["submit"] = "CONNEXION"


login_req = session.post(login_url, data=data, headers=h)

if login_req.url != home_page:        # MYGES IS A PIECE OF SHIT AND SOMETIMES DONT REDIRECT TO HOME PAGE 
    session.get(home_page, headers=h)

calendar_page = session.get(calendar_url, headers=h).text

view_state = re.findall(view_state_reg, calendar_page)[0]

n = datetime.now()

start = n - timedelta(days=n.weekday())
end = start + timedelta(days=7)

print(datetime.timestamp(start),datetime.timestamp(end))


data = {
    'javax.faces.partial.ajax': 'True',
    'javax.faces.source': 'calendar:myschedule',
    'javax.faces.partial.execute': 'calendar:myschedule',
    'javax.faces.partial.render': 'calendar:myschedule',
    'calendar:myschedule': 'calendar:myschedule',
    'calendar:myschedule_start': str(datetime.timestamp(start)),
    'calendar:myschedule_end': str(datetime.timestamp(end)),
    'calendar': 'calendar',
    'calendar:myschedule_view': 'agendaWeek',
    'javax.faces.ViewState': view_state
}


week_courses = session.post(calendar_url, data=data, headers=h).text

root = ElementTree.fromstring(week_courses)
planning = json.loads(root[0][0].text)

w = ""

embeds = {
    "embeds": []
}

for course in planning["events"]:
    start_date = parse(course["start"])
    end_date = parse(course["end"])
    if start_date.day == n.day and start_date.month == n.month and start_date.year == n.year:
        e = {
          "type": "rich",
          "title": f"De {start_date.strftime('%H:%M')} à {end_date.strftime('%H:%M')}",
          "description": "",
          "color": 0xe5cbcd,
          "fields": []
        }
        course_id = course["id"]
        data = {
            'javax.faces.partial.ajax': 'True',
            'javax.faces.source': 'calendar:myschedule',
            'javax.faces.partial.execute': 'calendar:myschedule',
            'javax.faces.partial.render': 'dlg1',
            'javax.faces.behavior.event': 'eventSelect',
            'javax.faces.partial.event': 'eventSelect',
            'calendar:myschedule_selectedEventId': course_id,
            'calendar': 'calendar',
            'calendar:myschedule_view': 'agendaWeek',
            'javax.faces.ViewState': view_state
        }

        course_desc = session.post(calendar_url, headers=h, data=data).text
        root = ElementTree.fromstring(course_desc)
        infos = root[0][0].text

        i = [(a[2],a[3]) for a in re.findall(desc_reg, infos) if a[2] !=  "duration"]

        labels = dict(i[::2])
        data = dict(i[1::2])

        print(labels, data, course)

        for l in labels:
            e["fields"].append(
                {
                  "name": f"**{labels[l].replace(' :','')}**",
                  "value": data[l],
                  "inline": True
                }
            )
        embeds["embeds"].append(e)

embeds["embeds"] = sorted(embeds["embeds"], key=lambda x:x["title"])
requests.post(config["webhook"], json=embeds)