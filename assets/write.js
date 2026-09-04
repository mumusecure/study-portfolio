/* mumu-os 글쓰기 콘솔
 *
 * GitHub Pages 는 정적 호스팅이라 글을 받아줄 서버가 없다.
 * 그래서 브라우저가 GitHub Contents API 로 직접 커밋한다.
 * 커밋이 올라가면 Actions 가 사이트를 다시 만든다.
 *
 * 토큰은 이 브라우저(localStorage)에만 있고 어디로도 전송되지 않는다.
 * (github.com 으로 가는 요청 외에는)
 */
(function () {
  "use strict";

  var CFG = window.WRITE_CFG || {};
  var TOKEN_KEY = "mumu-gh-token";
  var API = "https://api.github.com";
  var current = { name: "", sha: null };

  function $(id) { return document.getElementById(id); }

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
  }
  function setToken(t) {
    try {
      if (t) localStorage.setItem(TOKEN_KEY, t);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (e) {}
  }

  /* 한글이 섞인 UTF-8 문자열을 base64 로 (btoa 는 라틴1만 받는다) */
  function b64enc(str) {
    var bytes = new TextEncoder().encode(str), bin = "", i;
    for (i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }
  function b64dec(b64) {
    var bin = atob(String(b64).replace(/\s/g, ""));
    var bytes = new Uint8Array(bin.length), i;
    for (i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  /* build.py 의 slugify 와 같은 규칙 — 발행 후 주소를 알려주기 위해 */
  function slugify(s) {
    s = String(s).trim().toLowerCase().replace(/[\s_]+/g, "-");
    try { s = s.replace(/[^\p{L}\p{N}\-]/gu, ""); }
    catch (e) { s = s.replace(/[^\w\-]/g, ""); }
    return s.replace(/-{2,}/g, "-").replace(/^-+|-+$/g, "") || "note";
  }

  function status(msg, kind) {
    var el = $("w-status");
    el.textContent = msg;
    el.className = "w-status" + (kind ? " " + kind : "");
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch(API + path, {
      method: opts.method || "GET",
      headers: {
        Authorization: "Bearer " + getToken(),
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) {
          if (r.status === 401) throw new Error("토큰이 잘못됐거나 만료됐습니다.");
          if (r.status === 403) throw new Error("권한이 없습니다. 토큰에 Contents 쓰기 권한을 주세요.");
          if (r.status === 409) throw new Error("다른 곳에서 먼저 수정됐습니다. 목록에서 다시 불러오세요.");
          throw new Error(j.message || ("HTTP " + r.status));
        }
        return j;
      });
    });
  }

  function dirPath() {
    return "/repos/" + CFG.owner + "/" + CFG.repo + "/contents/" +
      CFG.dir.split("/").map(encodeURIComponent).join("/");
  }
  function filePath(name) {
    return dirPath() + "/" + encodeURIComponent(name);
  }

  /* ---------- 토큰 패널 ---------- */
  function renderTokenState() {
    var has = !!getToken();
    $("w-token-state").textContent = has ? "토큰 등록됨" : "토큰 없음";
    $("w-token-state").className = "w-badge " + (has ? "ok" : "warn");
    $("w-token-panel").hidden = has;
    $("w-forget").hidden = !has;
    $("w-editor").hidden = !has;
    if (has) loadList();
  }

  /* ---------- 노트 목록 ---------- */
  function loadList() {
    api(dirPath()).then(function (items) {
      var sel = $("w-list");
      sel.innerHTML = '<option value="">— 새 글 쓰기 —</option>';
      (items || [])
        .filter(function (i) { return i.type === "file" && /\.md$/i.test(i.name); })
        .forEach(function (i) {
          var o = document.createElement("option");
          o.value = i.name;
          o.textContent = i.name;
          sel.appendChild(o);
        });
      status("준비됨. 노트 " + (sel.options.length - 1) + "개.");
    }).catch(function (e) { status(e.message, "err"); });
  }

  function loadNote(name) {
    if (!name) {
      current = { name: "", sha: null };
      $("w-name").value = "";
      $("w-body").value = "";
      status("새 글 모드.");
      return;
    }
    status("불러오는 중…");
    api(filePath(name)).then(function (f) {
      current = { name: name, sha: f.sha };
      $("w-name").value = name.replace(/\.md$/i, "");
      $("w-body").value = b64dec(f.content);
      status("불러왔습니다. 고친 뒤 발행하세요.");
    }).catch(function (e) { status(e.message, "err"); });
  }

  /* ---------- 발행 ---------- */
  function publish() {
    var raw = $("w-name").value.trim();
    var body = $("w-body").value;
    if (!raw) { status("파일 이름을 입력하세요.", "err"); return; }
    if (!body.trim()) { status("본문이 비어 있습니다.", "err"); return; }

    var name = /\.md$/i.test(raw) ? raw : raw + ".md";
    var renamed = current.name && current.name !== name;
    var payload = {
      message: (current.sha ? "notes: " : "notes: ") + name.replace(/\.md$/i, "") + (current.sha ? " 수정" : " 추가"),
      content: b64enc(body),
      branch: CFG.branch
    };
    if (current.sha && !renamed) payload.sha = current.sha;

    $("w-publish").disabled = true;
    status("커밋하는 중…");

    api(filePath(name), { method: "PUT", body: payload })
      .then(function (res) {
        // 방금 만들어진 sha 를 들고 있어야 연달아 고칠 수 있다
        var newSha = (res && res.content && res.content.sha) || null;
        // 이름을 바꿔 저장했으면 옛 파일은 지운다
        if (renamed) {
          return api(filePath(current.name), {
            method: "DELETE",
            body: { message: "notes: " + current.name + " 이름 변경", sha: current.sha, branch: CFG.branch }
          }).then(function () { return newSha; });
        }
        return newSha;
      })
      .then(function (newSha) {
        var url = CFG.site + "wiki/" + encodeURIComponent(slugify(name.replace(/\.md$/i, ""))) + ".html";
        $("w-status").innerHTML =
          '올렸습니다. 사이트 반영까지 1분쯤 걸립니다 → <a href="' + url + '">' + url + "</a>";
        $("w-status").className = "w-status ok";
        current = { name: name, sha: newSha };
        loadList();
      })
      .catch(function (e) { status(e.message, "err"); })
      .then(function () { $("w-publish").disabled = false; });
  }

  /* ---------- 삭제 ---------- */
  function removeNote() {
    if (!current.name || !current.sha) { status("불러온 글이 없습니다.", "err"); return; }
    if (!confirm(current.name + " 을(를) 삭제할까요? 사이트에서도 사라집니다.")) return;
    status("삭제하는 중…");
    api(filePath(current.name), {
      method: "DELETE",
      body: { message: "notes: " + current.name + " 삭제", sha: current.sha, branch: CFG.branch }
    }).then(function () {
      status("삭제했습니다. 사이트 반영까지 1분쯤.", "ok");
      loadNote("");
      loadList();
    }).catch(function (e) { status(e.message, "err"); });
  }

  /* ---------- 초기화 ---------- */
  document.addEventListener("DOMContentLoaded", function () {
    $("w-save-token").addEventListener("click", function () {
      var t = $("w-token").value.trim();
      if (!t) { status("토큰을 붙여넣으세요.", "err"); return; }
      setToken(t);
      $("w-token").value = "";
      status("토큰을 저장했습니다.");
      renderTokenState();
    });
    $("w-forget").addEventListener("click", function () {
      setToken("");
      status("토큰을 지웠습니다.");
      renderTokenState();
    });
    $("w-list").addEventListener("change", function () { loadNote(this.value); });
    $("w-publish").addEventListener("click", publish);
    $("w-delete").addEventListener("click", removeNote);
    $("w-template").addEventListener("click", function () {
      if ($("w-body").value.trim() && !confirm("본문을 템플릿으로 덮어쓸까요?")) return;
      $("w-body").value = [
        "## 한 줄 요약", "", "## 왜 필요한가", "", "## 어떻게 동작하는가", "",
        "## 예제", "", "```python", "", "```", "", "## 막혔던 곳", "", "## 참고", "", "- "
      ].join("\n");
    });
    // ⌘/Ctrl + Enter 로 발행
    $("w-body").addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); publish(); }
    });
    renderTokenState();
  });
})();
