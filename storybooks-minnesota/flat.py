import detail

class Page(object):
    def page(self, offset=0):
        return "0"+str(self.number+offset)
    def __init__(self, i):
        self.number = i
        self.img = "url"
        self.lang = ["en", "es", "eg"]
        self.audio = "url"

page_objs = [Page(1), Page(2), Page(3)]

def effify(s):
    return eval(f'f"""{s}"""')

page_list = []
with open("html/page.template.html") as f:
    p_template = f.read()
    for page in page_objs:
        page_list.append(effify(p_template))

pages = "\n".join(page_list)

book = detail.MyFoundry(detail.url).book
print (book.foreigns)
with open("html/index.template.html") as f:
    template = f.read()
    f_template = effify(template)
with open("html/index.out.html", "w") as f:
    f.write(f_template)

