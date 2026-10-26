(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const layout = $("layout");
  const form = $("composer");
  const els = {
    title: $("title"), topic: $("topic"), styleUrl: $("style-url"),
    stageTitle: $("stage-title"), work: $("stage-work"), label: $("work-label"), bar: $("work-bar"),
    player: $("player"), go: $("go"), error: $("error"), notes: $("notes"),
    after: $("after"), download: $("download"), again: $("again"), engineNote: $("engine-note"),
    dialog: $("settings"), ghToken: $("gh-token"), ghRepo: $("gh-repo"),
    apiUrl: $("api-url"), apiKey: $("api-key"), status: $("settings-status"),
  };

  // ---------- settings (kept only in this browser) ----------
  const store = {
    get(k) { try { return localStorage.getItem(k) || ""; } catch { return ""; } },
    set(k, v) { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* private mode: lasts this visit only */ } },
  };

  // On GitHub Pages the address is <owner>.github.io/<repo>/, so the repo can be worked out.
  function inferRepo() {
    const host = location.hostname.match(/^([^.]+)\.github\.io$/i);
    const name = location.pathname.split("/")[1];
    return host && name ? `${host[1]}/${name}` : "";
  }
  const normalizeRepo = (v) =>
    v.trim().replace(/^https?:\/\/github\.com\//i, "").replace(/\.git$/i, "").replace(/\/+$/, "");

  const cfg = {
    url: store.get("friday.api"),
    key: store.get("friday.key"),
    token: store.get("friday.gh"),
    repo: store.get("friday.repo") || inferRepo(),
  };
  const mode = () => (cfg.url ? "engine" : cfg.token && cfg.repo ? "github" : "none");

  function failure(message, fatal = true, status = 0) {
    return Object.assign(new Error(message), { fatal, status });
  }

  // ---------- backend 1: your own engine (HTTP) ----------
  const base = () => cfg.url.replace(/\/+$/, "");

  async function engineCall(path, opts = {}) {
    const res = await fetch(base() + path, {
      ...opts,
      headers: { ...(cfg.key ? { "X-Friday-Key": cfg.key } : {}), ...(opts.headers || {}) },
    });
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail || ""; } catch { /* not JSON */ }
      if (res.status === 401) throw failure("The access key is missing or wrong. Open settings and enter it again.", true, 401);
      if (res.status === 404) throw failure("The engine restarted and lost this job. Start it again.", true, 404);
      throw failure(typeof detail === "string" && detail ? detail : `The engine answered with an error (${res.status}).`, true, res.status);
    }
    return res.json();
  }

  const engine = {
    interval: 1200,
    async health() {
      let h;
      try { h = await engineCall("/api/health"); } catch (e) {
        if (e.status) throw e;
        throw failure("Can't reach the engine. If it runs on a free host it may be waking up, so wait a minute and try again.", false);
      }
      return h.mode === "live" ? "" : "Demo mode: add script and footage keys on the engine for real results.";
    },
    async start(body) {
      const job = await engineCall("/api/jobs", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      return { id: job.id };
    },
    async poll(h) {
      const job = await engineCall(`/api/jobs/${h.id}`);
      if (job.status === "failed") throw failure(`The video couldn't be finished: ${job.error}. Try again, or shorten the topic.`);
      if (job.status !== "done") return { state: "running", progress: job.progress, label: job.label };
      const q = cfg.key ? `?key=${encodeURIComponent(cfg.key)}` : "";
      return {
        state: "done", progress: 100, label: job.label, warnings: job.warnings,
        videoUrl: `${base()}/api/jobs/${h.id}/video${q}`,
      };
    },
  };

  // ---------- backend 2: GitHub Actions (free, no server) ----------
  const GH = "https://api.github.com";
  // Step names match .github/workflows/render.yml; weights add up to 100.
  const STEPS = [
    ["Preparing", 5], ["Installing video tools", 15], ["Installing Friday", 5],
    ["Installing Friday packages", 10], ["Writing, voicing and rendering", 55], ["Publishing your video", 10],
  ];

  async function ghCall(path, opts = {}) {
    let res;
    try {
      res = await fetch(GH + path, {
        ...opts,
        headers: {
          Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
          Authorization: `Bearer ${cfg.token}`, ...(opts.headers || {}),
        },
      });
    } catch {
      throw failure("Can't reach GitHub. Check your connection.", false);
    }
    if (res.status === 204) return null;
    let data = null;
    try { data = await res.json(); } catch { /* empty body */ }
    if (res.ok) return data;
    const msg = (data && data.message) || "";
    if (res.status === 401) throw failure("GitHub rejected the token. Create a new one and paste it in settings.", true, 401);
    if (res.status === 403 && /rate limit/i.test(msg)) throw failure("GitHub is limiting requests for a moment.", false, 403);
    if (res.status === 403) throw failure("The token can't run workflows. Give it Actions: read and write on this repository.", true, 403);
    if (res.status === 404) throw failure("GitHub can't find that repository or its Render workflow. Check the repository name and the token's access.", true, 404);
    if (res.status === 422) throw failure(`GitHub refused the request${msg ? `: ${msg}` : ""}.`, true, 422);
    throw failure(`GitHub answered with an error (${res.status}).`, res.status >= 500, res.status);
  }

  const randomId = () => Array.from(crypto.getRandomValues(new Uint8Array(6)), (b) => b.toString(16).padStart(2, "0")).join("");

  const github = {
    interval: 4000,
    branch: "",
    async health() {
      const repo = await ghCall(`/repos/${cfg.repo}`);
      this.branch = repo.default_branch;
      return "Renders on GitHub, so a video takes a few minutes.";
    },
    async start(body) {
      if (!this.branch) await this.health();
      const id = randomId();
      await ghCall(`/repos/${cfg.repo}/actions/workflows/render.yml/dispatches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ref: this.branch,
          inputs: {
            job_id: id, title: body.title, topic: body.topic,
            aspect: body.aspect, seconds: String(body.seconds), style_url: body.style_url, kind: body.kind,
          },
        }),
      });
      return { id, startedAt: Date.now() };
    },
    async poll(h) {
      const runs = await ghCall(`/repos/${cfg.repo}/actions/workflows/render.yml/runs?event=workflow_dispatch&per_page=20`);
      const wanted = `Friday ${h.id}`;
      const run = runs.workflow_runs.find((r) => r.display_title === wanted || r.name === wanted);
      if (!run) {
        if (Date.now() - h.startedAt > 420000) {
          throw failure("GitHub didn't start the render. Check that Actions is enabled and the Render workflow is on the default branch.");
        }
        return { state: "running", progress: 4, label: "Sending to GitHub" };
      }
      if (run.status === "completed") {
        if (run.conclusion !== "success") {
          throw failure(`The render job ended with "${run.conclusion}". Details: ${run.html_url}`);
        }
        return this.finish(h);
      }
      const data = await ghCall(`/repos/${cfg.repo}/actions/runs/${run.id}/jobs`);
      const steps = (data.jobs[0] && data.jobs[0].steps) || [];
      let progress = 0;
      let label = run.status === "queued" ? "Waiting for a GitHub runner" : "Starting up";
      for (const [name, weight] of STEPS) {
        const s = steps.find((x) => x.name === name);
        if (s && s.status === "completed") progress += weight;
        else {
          if (s && s.status === "in_progress") { progress += weight / 2; label = name; }
          break;
        }
      }
      return { state: "running", progress: Math.max(5, progress), label };
    },
    async finish(h) {
      let release;
      try { release = await ghCall(`/repos/${cfg.repo}/releases/tags/friday-${h.id}`); } catch (e) {
        if (e.status === 404) throw failure("The render finished but its video wasn't published. Open the run on GitHub to see why.");
        throw e;
      }
      const asset = (release.assets || []).find((a) => a.name === "video.mp4");
      if (!asset) throw failure("The render finished but the video file is missing. Try again.");
      return {
        state: "done", progress: 100, label: "Your video is ready",
        warnings: (release.body || "").split("\n").map((s) => s.trim()).filter(Boolean),
        videoUrl: asset.browser_download_url, assetApi: asset.url,
      };
    },
    // If the browser won't stream the public link, fetch it with the token instead.
    async blob(assetApi) {
      const res = await fetch(assetApi, { headers: { Accept: "application/octet-stream", Authorization: `Bearer ${cfg.token}` } });
      if (!res.ok) throw failure("Couldn't download the video.");
      return URL.createObjectURL(await res.blob());
    },
  };

  const pick = () => ({ engine, github, none: null }[mode()]);

  // ---------- state ----------
  let state = "idle";
  let backend = null;
  let pollTimer = 0;
  let retries = 0;
  let lastAsset = "";
  let blobTried = false;

  function setState(next) {
    state = next;
    layout.dataset.state = next;
    const running = next === "running";
    const done = next === "done";
    els.go.disabled = running;
    els.go.hidden = done;
    els.go.textContent = running ? "Working" : "Generate video";
    els.work.hidden = !running;
    els.after.hidden = !done;
    els.player.hidden = !done;
    els.stageTitle.hidden = done;
    form.querySelectorAll("input, textarea").forEach((el) => { el.disabled = running; });
  }

  // On phones the stage sits above the form, so bring it back into view.
  function showStage() {
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: calm ? "auto" : "smooth" });
  }

  function showError(message) {
    els.error.textContent = message;
    els.error.hidden = !message;
  }

  function showNotes(list) {
    els.notes.replaceChildren(...(list || []).map((t) => Object.assign(document.createElement("li"), { textContent: t })));
    els.notes.hidden = !list || !list.length;
  }

  // ---------- live title on the stage ----------
  function syncTitle() {
    const value = els.title.value.trim();
    els.stageTitle.textContent = value || "Your title appears here";
    els.stageTitle.dataset.empty = value ? "false" : "true";
  }
  els.title.addEventListener("input", syncTitle);

  form.addEventListener("change", (e) => {
    if (e.target.name === "aspect") layout.dataset.aspect = e.target.value;
    if (e.target.name === "kind") {
      $("kind-hint").textContent = {
        explainer: "Animated charts, numbers and text drawn by code. No stock clips.",
        motion: "Bold kinetic type, 3D shapes and app scenes, drawn by code. No stock clips.",
      }[e.target.value] || "Real video clips matched to every line.";
    }
  });

  // ---------- connection status ----------
  async function refreshBackend() {
    backend = pick();
    let note = "";
    let ok = true;
    if (!backend) {
      note = "Add your GitHub token in settings to start making videos.";
      ok = false;
    } else {
      try { note = await backend.health(); } catch (e) { note = e.message; ok = false; }
    }
    els.engineNote.textContent = note;
    els.engineNote.hidden = !note;
    return { ok, note };
  }

  // ---------- generate ----------
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state === "running") return;
    showError("");
    showNotes([]);

    const title = els.title.value.trim();
    if (!title) {
      showError("Add a title to start.");
      els.title.focus();
      return;
    }
    backend = pick();
    if (!backend) {
      showError("Add your GitHub token in settings first. It takes a minute.");
      openSettings();
      return;
    }

    const data = new FormData(form);
    const body = {
      title,
      topic: els.topic.value.trim(),
      kind: data.get("kind") || "footage",
      aspect: data.get("aspect"),
      seconds: Number(data.get("seconds")),
      style_url: els.styleUrl.value.trim(),
    };

    setState("running");
    showStage();
    els.label.textContent = "Sending your request";
    els.bar.style.width = "3%";
    retries = 0;

    try {
      const handle = await backend.start(body);
      store.set("friday.job", JSON.stringify({ mode: mode(), handle, title, startedAt: Date.now() }));
      loop(handle, title);
    } catch (err) {
      abort(err);
    }
  });

  function abort(err) {
    clearTimeout(pollTimer);
    store.set("friday.job", "");
    setState("idle");
    showError(err instanceof Error ? err.message : String(err));
  }

  function loop(handle, title) {
    clearTimeout(pollTimer);
    const tick = async () => {
      try {
        const r = await backend.poll(handle);
        retries = 0;
        els.label.textContent = r.label;
        els.bar.style.width = `${Math.max(3, r.progress)}%`;
        if (r.state === "done") return finish(r, title);
        pollTimer = setTimeout(tick, backend.interval);
      } catch (err) {
        if (err.fatal) return abort(err);
        // A network blip should not kill a render that is still running.
        retries += 1;
        if (retries > 8) return abort("Lost contact with the render. Check your connection and try again.");
        pollTimer = setTimeout(tick, 3000 * Math.min(retries, 4));
      }
    };
    tick();
  }

  function finish(result, title) {
    store.set("friday.job", "");
    lastAsset = result.assetApi || "";
    blobTried = false;
    els.player.src = result.videoUrl;
    els.download.href = result.videoUrl;
    els.download.setAttribute("download", `${title.replace(/[^\w -]+/g, "").trim() || "friday"}.mp4`);
    setState("done");
    showStage();
    showNotes(result.warnings);
    els.player.play().catch(() => { /* autoplay with sound may be blocked; controls are visible */ });
  }

  els.player.addEventListener("error", async () => {
    if (!lastAsset || blobTried || !backend || !backend.blob) return;
    blobTried = true;
    try {
      const url = await backend.blob(lastAsset);
      els.player.src = url;
      els.download.href = url;
    } catch { /* the Download button still opens the public link */ }
  });

  els.again.addEventListener("click", () => {
    els.player.pause();
    els.player.removeAttribute("src");
    els.player.load();
    showNotes([]);
    showError("");
    setState("idle");
    els.title.value = "";
    els.topic.value = "";
    syncTitle();
    els.title.focus();
  });

  // ---------- settings dialog ----------
  function openSettings() {
    els.ghToken.value = cfg.token;
    els.ghRepo.value = cfg.repo;
    els.apiUrl.value = cfg.url;
    els.apiKey.value = cfg.key;
    els.status.textContent = "";
    els.status.dataset.ok = "";
    els.dialog.showModal();
  }
  $("open-settings").addEventListener("click", openSettings);

  $("save-settings").addEventListener("click", async () => {
    cfg.token = els.ghToken.value.trim();
    cfg.repo = normalizeRepo(els.ghRepo.value);
    cfg.url = els.apiUrl.value.trim();
    cfg.key = els.apiKey.value.trim();
    store.set("friday.gh", cfg.token);
    store.set("friday.repo", cfg.repo === inferRepo() ? "" : cfg.repo);
    store.set("friday.api", cfg.url);
    store.set("friday.key", cfg.key);
    els.status.textContent = "Testing";
    els.status.dataset.ok = "";
    if (github) github.branch = "";
    const { ok, note } = await refreshBackend();
    els.status.textContent = ok ? (mode() === "github" ? `Connected to ${cfg.repo}.` : "Connected.") : note;
    els.status.dataset.ok = String(ok);
  });

  // ---------- start ----------
  setState("idle");
  syncTitle();
  refreshBackend().then(() => {
    // Pick up a render that was running when the page was closed.
    let saved = null;
    try { saved = JSON.parse(store.get("friday.job") || "null"); } catch { /* ignore */ }
    if (!saved || saved.mode !== mode() || Date.now() - saved.startedAt > 40 * 60 * 1000 || !backend) {
      store.set("friday.job", "");
      return;
    }
    els.title.value = saved.title;
    syncTitle();
    setState("running");
    els.label.textContent = "Picking up where you left off";
    loop(saved.handle, saved.title);
  });

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("sw.js").catch(() => { /* the app still works without offline support */ });
  }
})();
