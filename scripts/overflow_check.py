from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch()
    for w in (360,412):
        m=b.new_page(viewport={"width":w,"height":800}); m.goto("http://localhost:4173/"); m.wait_for_timeout(3000)
        print(w, m.evaluate("document.documentElement.scrollWidth"))
        print(m.evaluate(f"""[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>{w}+1 && e.children.length<3).slice(0,12).map(e=>e.tagName+'.'+e.className+' r='+Math.round(e.getBoundingClientRect().right)+' '+(e.innerText||'').slice(0,30))"""))
    b.close()
