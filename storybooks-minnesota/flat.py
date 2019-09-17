import detail

def effify(s):
    return eval(f'f"""{s}"""')

book = detail.MyFoundry(detail.url).book
print (book.foreigns)
with open("html/index.template.html") as f:
    template = f.read()
    f_template = effify(template)
with open("html/index.out.html", "w") as f:
    f.write(f_template)

