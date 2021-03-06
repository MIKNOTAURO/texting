from sms.management.commands.campaign import *
from sms.management.commands.read_in import read_in

FOLLOWUP_DAYS_BACK = 5  # this could be 2 if followup runs daily without errors
ALT_FOLLOWUP_CATEGORIES = ['Alt', 'Whole']


def sort_by_sim(followup):
     # sort by SIM, so followups go out from the same SIM
    sims = {}
    for m in followup:
        ls = sims.setdefault(m.sim, [])
        ls.append(m.no)
    return sims


def choose_modem_by_sim(devices, sim):
    """Return modem containing the SIM, None if no modem has it.
    """
    try: return [x for x in devices if x['sim']==sim][0]['modem']
    except IndexError: return


def send_followups(devices, followups, txt):
    followup_sims = sort_by_sim(followups)
    print(txt)
    for sim, numbers in followup_sims.items():
        modem = choose_modem_by_sim(devices, sim)
        for no in numbers:
            if not duplicates(no):
                send_one_text(modem, sim, txt, no)
                print('|', end="")
            else:
                print('-', end="")


def followup():
    """Followup runs once a day to avoid duplicates
    """
    BASIC_FOLLOWUP_TXT = Tpl.objects.get(name='Followup')
    ALT_FOLLOWUP_TXT = Tpl.objects.get(name='Followup alternative')

    # FINGERPRINT is used to discern 1st text from a followup
    FINGERPRINT = Tpl.objects.get(name='FINGERPRINT')

    now = datetime.now()
    # take 1st campaign texts sent 24 hours ago up to FOLLOWUP_DAYS_BACK
    sent = Sms.objects.filter(typ='s',
        txt__contains=FINGERPRINT.tpl,
        at__range=(now - timedelta(days=FOLLOWUP_DAYS_BACK), now - timedelta(days=1)))
    rpls = Sms.objects.filter(typ='r',
        at__range=(now - timedelta(days=FOLLOWUP_DAYS_BACK), now))
    d={}
    for s in sent:
        d[s.no] = [s]
    for r in rpls:
        try: d[r.no] = d[r.no]+[r]
        except KeyError: pass # replies to later texts

    basic_followup = []
    alt_followup = []
    ignoring_texts = []
    for no, dialog in d.items():
        msg = dialog[0]
        # if no reply use default followup
        if len(dialog) < 2:
            basic_followup.append(msg)
        # followup based on reply category
        else:
            reply = dialog[-1]
            if reply.cat:
                if reply.cat.name in ('Thanks', 'Misc'):
                    basic_followup.append(msg)
                elif reply.cat.name in ALT_FOLLOWUP_CATEGORIES:
                    alt_followup.append(msg)
                else: # ignore 'Bot' & 'End' categories
                    ignoring_texts.append(reply)
            else: # ignore uncategorised
                ignoring_texts.append(reply)

    devices, _modem, _info = list_devices()

    send_followups(devices, basic_followup, BASIC_FOLLOWUP_TXT.tpl)
    send_followups(devices, alt_followup, ALT_FOLLOWUP_TXT.tpl)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        read_in()
        followup()
