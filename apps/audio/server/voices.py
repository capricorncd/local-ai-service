"""Built-in Qwen speakers. VC references are generated locally by this app."""
VOICES = [
    {'id':'vivian','name':'薇薇安','description':'明亮年轻女声 · 中文','language':'Chinese'},
    {'id':'serena','name':'瑟琳娜','description':'温柔温暖女声 · 中文','language':'Chinese'},
    {'id':'uncle_fu','name':'福叔','description':'低沉醇厚男声 · 中文','language':'Chinese'},
    {'id':'dylan','name':'迪伦','description':'清亮年轻男声 · 北京话','language':'Chinese'},
    {'id':'eric','name':'埃里克','description':'活泼男声 · 四川话','language':'Chinese'},
    {'id':'ryan','name':'瑞恩','description':'有节奏的动感男声 · 英文','language':'English'},
    {'id':'aiden','name':'艾登','description':'清晰沉稳男声 · 英文','language':'English'},
    {'id':'ono_anna','name':'小野杏','description':'轻快灵动女声 · 日文','language':'Japanese'},
    {'id':'sohee','name':'素熙','description':'温暖有情感的女声 · 韩文','language':'Korean'},
]
VOICE_IDS = {voice['id'] for voice in VOICES}
