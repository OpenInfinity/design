(function () {
  "use strict";
  var data = window.OI_DATA || { files: [], palette: [], headSnippet: "" };
  var root = document.documentElement;
  var KEY = "oi-lang";
  var TITLES = { zh: "OpenInfinity 设计资源", en: "OpenInfinity Design Resources" };

  function getStored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function store(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* private mode */ }
  }
  function setLang(lang) {
    root.setAttribute("data-lang", lang);
    root.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = TITLES[lang];
  }
  var param = new URLSearchParams(location.search).get("lang");
  setLang(param === "en" || param === "zh" ? param : getStored() === "en" ? "en" : "zh");
  document.getElementById("lang").addEventListener("click", function () {
    var next = root.getAttribute("data-lang") === "zh" ? "en" : "zh";
    setLang(next);
    store(next);
  });

  function size(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }
  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text != null) n.textContent = text;
    return n;
  }
  function bi(zh, en) {
    var f = document.createDocumentFragment();
    f.appendChild(el("span", { class: "zh" }, zh));
    f.appendChild(el("span", { class: "en" }, en));
    return f;
  }

  var toast = document.getElementById("toast");
  var timer;
  function copy(text) {
    var done = function () {
      toast.textContent = root.getAttribute("data-lang") === "zh" ? "已复制 " + text : "Copied " + text;
      toast.classList.add("show");
      clearTimeout(timer);
      timer = setTimeout(function () { toast.classList.remove("show"); }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, done);
    } else {
      var t = el("textarea");
      t.value = text;
      document.body.appendChild(t);
      t.select();
      try { document.execCommand("copy"); } catch (e) { /* ignore */ }
      t.remove();
      done();
    }
  }

  // download chips
  document.querySelectorAll("[data-files]").forEach(function (box) {
    var prefixes = box.getAttribute("data-files").split(",");
    var collator = new Intl.Collator("en", { numeric: true });
    data.files.filter(function (f) {
      return prefixes.some(function (p) { return f.path.indexOf(p) === 0; });
    }).sort(function (a, b) { return collator.compare(a.path, b.path); }).forEach(function (f) {
      var parts = f.path.split("/");
      var name = parts[parts.length - 1];
      var folder = parts[parts.length - 2] || "";
      var label = name.replace(/^openinfinity-/, "").replace(new RegExp("^" + folder + "-"), "");
      var a = el("a", { href: "assets/" + f.path, download: name, title: f.path }, label + " ");
      a.appendChild(el("small", null, size(f.bytes)));
      box.appendChild(a);
    });
  });

  // palette
  var pal = document.getElementById("palette");
  data.palette.forEach(function (c) {
    var light = (c.rgb[0] * 299 + c.rgb[1] * 587 + c.rgb[2] * 114) / 1000 > 140;
    var card = el("div", { class: "card swatch" });
    var chip = el("div", { class: "chip" });
    chip.style.background = c.hex;
    chip.style.color = light ? "#000" : "#fff";
    if (c.hex.toUpperCase() === "#FFFFFF" || c.hex.toUpperCase() === "#F5F5F4") chip.style.borderBottom = "1px solid #e5e5e5";
    chip.appendChild(bi(c.name.zh + " " + c.name.en, c.name.en + " · " + c.name.zh));
    card.appendChild(chip);
    var body = el("div", { class: "body" });
    body.appendChild(el("p")).appendChild(bi(c.role.zh, c.role.en));
    var codes = el("div", { class: "codes" });
    [["HEX", c.hex], ["RGB", c.rgb.join(" ")], ["CMYK", c.cmyk.join(" ")]].forEach(function (row) {
      var b = el("button", { type: "button", "aria-label": "Copy " + row[0] + " " + row[1] });
      b.appendChild(el("span", null, row[1]));
      b.appendChild(el("span", null, row[0]));
      b.addEventListener("click", function () { copy(row[1]); });
      codes.appendChild(b);
    });
    body.appendChild(codes);
    card.appendChild(body);
    pal.appendChild(card);
  });

  // head snippet + copy buttons
  var pre = document.getElementById("head-snippet");
  if (pre) pre.textContent = data.headSnippet;
  document.querySelectorAll("[data-copy-target]").forEach(function (b) {
    b.addEventListener("click", function () {
      copy(document.getElementById(b.getAttribute("data-copy-target")).textContent);
    });
  });

  // totals
  var count = document.getElementById("file-count");
  if (count) {
    var total = data.files.reduce(function (s, f) { return s + f.bytes; }, 0);
    count.appendChild(bi(data.files.length + " 个文件，约 " + size(total), data.files.length + " files, about " + size(total)));
  }
})();
