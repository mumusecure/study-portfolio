/* mumu-os client scripts: boot sequence / fake terminal / konami */
(function () {
  "use strict";

  var MASCOT = [
    "      \\\\|//",
    "     \\\\|||//",
    "      \\|||/",
    "    .-------.",
    "    |  [] []|   < 무무",
    "    |   __  |",
    "    '.  \\/ .'",
    "      \\   /",
    "      |   |",
    "       \\ /",
    "        V"
  ].join("\n");

  /* ---------- boot sequence (index only) ---------- */
  var boot = document.getElementById("boot");
  if (boot) {
    if (sessionStorage.getItem("mumu-booted")) {
      boot.remove();
    } else {
      var lines = [
        "MUMU-OS v0.1  (study-portfolio kernel)",
        "[  OK  ] 암호화 모듈 로드: lattice.ko, mlkem.ko",
        "[  OK  ] /var/log/fails 마운트 (사용량 87%)",
        "[  OK  ] 학습 잔디 데몬 시작",
        "[ WARN ] 게으름 프로세스 감지됨 → kill -9 실패",
        "[  OK  ] 사용자 로그인: mumu",
        "",
        "환영합니다. 무무의 학습 관제 센터입니다."
      ];
      var pre = document.createElement("pre");
      boot.appendChild(pre);
      var skip = document.createElement("div");
      skip.className = "skip";
      skip.textContent = "[클릭해서 건너뛰기]";
      boot.appendChild(skip);
      var i = 0;
      var done = function () {
        sessionStorage.setItem("mumu-booted", "1");
        boot.remove();
      };
      var tick = function () {
        if (!document.body.contains(boot)) return;
        if (i >= lines.length) { setTimeout(done, 600); return; }
        pre.textContent += lines[i] + "\n";
        i++;
        setTimeout(tick, i <= 1 ? 500 : 220);
      };
      boot.addEventListener("click", done);
      tick();
    }
  }

  /* ---------- fake terminal (index only) ---------- */
  var termOut = document.getElementById("term-out");
  var termIn = document.getElementById("term-in");
  if (termOut && termIn) {
    var PS1 = "mumu@study:~$ ";
    var print = function (s) {
      termOut.textContent += s + "\n";
      termOut.scrollTop = termOut.scrollHeight;
    };
    var FILES = "about.html   fails.html   me.html   skills.html   timeline.html   wiki/";
    var CMDS = {
      help: function () {
        print("사용 가능한 명령어:");
        print("  help          이 목록");
        print("  ls [-la]      파일 목록");
        print("  cat <파일>    파일 내용 보기");
        print("  whoami        내가 누구게");
        print("  open <페이지> 페이지로 이동 (예: open skills)");
        print("  mumu          마스코트 소환");
        print("  clear         화면 지우기");
        print("  write         글쓰기 콘솔 열기");
        print("  ...숨겨진 것들은 직접 찾아보세요");
      },
      ls: function (args) {
        if (args.indexOf("-la") >= 0 || args.indexOf("-al") >= 0 || args.indexOf("-a") >= 0) {
          print("drwxr-xr-x  mumu  .");
          print("drwxr-xr-x  mumu  ..");
          print("-rw-------  mumu  .secret");
          print("-rw-r--r--  mumu  " + FILES);
        } else {
          print(FILES);
        }
      },
      cat: function (args) {
        var f = args[0];
        if (!f) { print("cat: 파일명을 입력하세요"); return; }
        if (f === ".secret") {
          print("cm90MTM6ZnJwZXJnL2luaHlnLnVnenk=");
          print("# 암호학 공부한 보람이 있기를.");
        } else {
          print("cat: " + f + ": 그런 파일 없음 (ls -la 는 해보셨나요?)");
        }
      },
      whoami: function () {
        print("무무 — 컴퓨터공학부 4학년, PQC와 보안을 공부하는 채소 무 해커.");
      },
      mumu: function () { print(MASCOT); },
      open: function (args) {
        var p = (args[0] || "").replace(".html", "");
        var pages = { skills: "skills.html", wiki: "wiki/index.html", timeline: "timeline.html", fails: "fails.html", me: "me.html", about: "about.html", logs: "logs.html", write: "write.html" };
        if (pages[p]) { print("이동 중..."); location.href = pages[p]; }
        else print("open: " + (args[0] || "?") + ": 그런 페이지 없음");
      },
      clear: function () { termOut.textContent = ""; },
      date: function () { print(new Date().toString()); },
      uname: function () { print("MUMU-OS 0.1 study-portfolio x86_64 (사실 그냥 정적 사이트)"); },
      pwd: function () { print("/home/mumu/study"); },
      exit: function () { print("어딜 나가려고요. 공부해야죠."); },
      write: function () { print("글쓰기 콘솔로 이동합니다..."); location.href = "write.html"; }
    };
    var runCommand = function () {
      var raw = termIn.value.trim();
      termIn.value = "";
      print(PS1 + raw);
      if (!raw) return;
      var parts = raw.split(/\s+/);
      var cmd = parts[0];
      var args = parts.slice(1);
      if (cmd === "sudo") {
        if (raw.indexOf("coffee") >= 0) print("sudo: 권한 상승 실패 — 커피는 직접 내리세요.");
        else print("sudo: 이 시도는 /var/log/fails 에 기록되었습니다. (농담)");
        return;
      }
      if (CMDS[cmd]) CMDS[cmd](args);
      else print("command not found: " + cmd + " — help 를 입력해보세요");
    };
    var termForm = document.getElementById("term-form");
    if (termForm) {
      termForm.addEventListener("submit", function (e) { e.preventDefault(); runCommand(); });
    }
    termIn.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); runCommand(); } });
    document.querySelector(".term").addEventListener("click", function () { termIn.focus(); });
    print("mumu-os 터미널입니다. help 를 입력해보세요.");
  }

  /* ---------- konami code: mascot dance (all pages) ---------- */
  var seq = ["ArrowUp","ArrowUp","ArrowDown","ArrowDown","ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","b","a"];
  var pos = 0;
  var dance = document.createElement("pre");
  dance.id = "mascot-dance";
  dance.className = "ascii";
  document.addEventListener("keydown", function (e) {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) {
      pos = 0; return;
    }
    pos = (e.key === seq[pos]) ? pos + 1 : (e.key === seq[0] ? 1 : 0);
    if (pos === seq.length) {
      pos = 0;
      if (!dance.parentNode) document.body.appendChild(dance);
      dance.textContent = " ♪\n" + MASCOT.replace("< 무무", "< 춤추는 무무") + "\n ♪ 코나미 코드 발견!";
      dance.classList.add("on");
      setTimeout(function () { dance.classList.remove("on"); }, 6000);
    }
  });
})();
