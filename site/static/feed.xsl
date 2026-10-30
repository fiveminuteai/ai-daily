<?xml version="1.0" encoding="UTF-8"?>
<!-- Browsers apply this to feed.xml so a person who clicks the RSS link sees a page, not raw XML.
     Feed readers ignore it and read the RSS as before. Paths are relative to feed.xml at the site root. -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" encoding="UTF-8" indent="yes"/>
<xsl:template match="/rss/channel">
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="robots" content="noindex"/>
  <title>RSS feed · <xsl:value-of select="title"/></title>
  <link rel="icon" href="assets/icon.svg" type="image/svg+xml"/>
  <link rel="stylesheet" href="assets/style.css"/>
  <script>try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}</script>
  <style>
    body { background: var(--bg); color: var(--ink); font-family: var(--text); margin: 0; }
    .fw { max-width: 720px; margin: 0 auto; padding: var(--s7) var(--s4) var(--s8); }
    .fw-brand { font-family: var(--display); font-weight: 700; color: var(--ink); text-decoration: none; font-size: 1.05rem; }
    .fw h1 { font-family: var(--display); font-size: clamp(2rem, 6vw, 2.8rem); line-height: 1.05; margin: var(--s6) 0 var(--s3); }
    .fw-lede { color: var(--ink-2); font-size: 1.05rem; line-height: 1.6; margin: 0 0 var(--s5); }
    .fw-box { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); padding: var(--s5); }
    .fw-box p { margin: 0 0 var(--s3); color: var(--muted); font-size: .95rem; line-height: 1.55; }
    .fw-url { display: flex; gap: var(--s2); flex-wrap: wrap; }
    .fw-url code { flex: 1 1 260px; min-width: 0; white-space: nowrap; overflow-x: auto; font-family: var(--mono); font-size: .88rem;
                   background: var(--bg-2); border: 1px solid var(--line-2); border-radius: var(--r-sm); padding: 10px 12px; color: var(--ink); }
    .fw-btn { font: 600 .95rem var(--text); background: var(--accent); color: var(--on-accent); border: 0; border-radius: var(--r-sm);
              padding: 10px 16px; cursor: pointer; transition: transform .12s var(--ease); }
    .fw-btn:active { transform: scale(.98); }
    .fw-btn:focus-visible, .fw a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .fw h2 { font-family: var(--display); font-size: 1.15rem; margin: var(--s7) 0 var(--s3); color: var(--ink-2); }
    .fw ol { list-style: none; padding: 0; margin: 0; }
    .fw li { padding: var(--s4) 0; border-top: 1px solid var(--line); }
    .fw li a { color: var(--ink); text-decoration: none; font-family: var(--display); font-weight: 700; font-size: 1.15rem; line-height: 1.3; }
    .fw li a:hover { color: var(--accent); }
    .fw-date { display: block; color: var(--faint); font-size: .85rem; margin-bottom: var(--s1); }
    .fw-dek { margin: var(--s2) 0 0; color: var(--muted); line-height: 1.55; }
    .fw-foot { margin-top: var(--s6); color: var(--faint); font-size: .9rem; }
    .fw-foot a { color: var(--ink-2); }
  </style>
</head>
<body>
  <main class="fw">
    <a class="fw-brand" href="{link}"><xsl:value-of select="title"/></a>
    <h1>This is the RSS feed</h1>
    <p class="fw-lede">Follow <xsl:value-of select="title"/> in a feed reader and each day's post arrives on its own, around 05:45 India time. No account or email needed.</p>
    <div class="fw-box">
      <p>Copy this address and paste it into any reader, such as Feedly, Inoreader, NetNewsWire or Thunderbird.</p>
      <div class="fw-url">
        <code id="feed-url"><xsl:value-of select="concat(link, 'feed.xml')"/></code>
        <button class="fw-btn" type="button" id="copy">Copy address</button>
      </div>
    </div>
    <h2>Latest posts</h2>
    <ol>
      <xsl:for-each select="item">
        <li>
          <span class="fw-date"><xsl:value-of select="substring(pubDate, 1, 16)"/></span>
          <a href="{link}"><xsl:value-of select="title"/></a>
          <p class="fw-dek"><xsl:value-of select="description"/></p>
        </li>
      </xsl:for-each>
    </ol>
    <p class="fw-foot">Or just read it on the site: <a href="{link}"><xsl:value-of select="substring-after(substring-before(concat(link, '#'), '#'), '://')"/></a></p>
  </main>
  <script><![CDATA[
    (function(){var b=document.getElementById("copy"),u=document.getElementById("feed-url");if(!b||!u)return;
      b.addEventListener("click",function(){var done=function(){b.textContent="Copied";setTimeout(function(){b.textContent="Copy address"},1600)};
        var select=function(){var r=document.createRange();r.selectNodeContents(u);var s=getSelection();s.removeAllRanges();s.addRange(r);
          b.textContent="Selected, press Ctrl+C";setTimeout(function(){b.textContent="Copy address"},2400)};
        if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(u.textContent.trim()).then(done,select);else select()});})();
  ]]></script>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
