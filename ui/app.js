"use strict";
const $ = (id) => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem("robot-session") || "";
if (token) sessionStorage.setItem("robot-session", token);
// The credential stays in session storage, out of subsequent URL copies.
history.replaceState(null, "", location.pathname);
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let state = "warmup", revision = -1, connected = false, pending = false, voice = true;
let renderedMessages = [], localEcho = null, preview = false, chatOpen = false;
let deviceLoading = false;
let gaze = {x: 0, y: 0}, target = {x: 0, y: 0}, greetingUntil = 0;
const statuses = {
  idle: ["Ready when you are", "Say “Hey In Site” or tap the microphone"],
  warmup: ["Getting comfortable", "Your companion is starting up"],
  listening: ["I’m all ears", "Go ahead, I’m listening to you"],
  transcribing: ["Got it", "Turning your words into text"],
  thinking: ["Connecting the dots", "Giving your question a little thought"],
  searching: ["A little exploring", "Looking for answers on the web"],
  capturing: ["Taking a closer look", "Making sense of what’s around us"],
  speaking: ["Something to share", "Here’s what I found for you"],
  error: ["A small interruption", "Check the assistant terminal for details"]
};
async function api(path, data) {
  const response = await fetch(path, {method: data === undefined ? "GET" : "POST", headers: {"Authorization": `Bearer ${token}`, ...(data === undefined ? {} : {"Content-Type": "application/json"})}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Something went wrong. Please try again.");
  return result;
}
function notice(message = "") { $("notice").textContent = message; $("notice").classList.toggle("hidden", !message); }
function updateControls() {
  const busy = !connected || pending || !["idle", "listening"].includes(state);
  $("send").disabled = busy;
  $("listen").disabled = busy || state === "listening";
  $("camera").disabled = busy;
  document.querySelectorAll("[data-prompt]").forEach(button => button.disabled = busy);
  $("listen").classList.toggle("listening", state === "listening");
  $("listen").querySelector("span").textContent = state === "listening" ? "Listening…" : "Talk to me";
  $("devices-save").disabled = deviceLoading || !["idle", "error"].includes(state);
}
function updateState(next) {
  state = next;
  const [title, subtitle] = statuses[state] || statuses.idle;
  $("presence-title").textContent = title;
  $("presence-subtitle").textContent = subtitle;
  $("waveform").classList.toggle("active", ["listening", "speaking"].includes(state));
  const working = ["thinking", "searching", "capturing", "transcribing"].includes(state);
  $("thinking").classList.toggle("hidden", !working);
  $("thinking").querySelector("em").textContent = {searching: "Exploring the web…", capturing: "Taking a look…", thinking: "One moment…"}[state] || "One moment…";
  updateControls();
}
function appendMessage(message) {
  const article = document.createElement("article");
  article.className = `message ${message.role === "user" ? "user" : "assistant"}`;
  const heading = document.createElement("div"); heading.className = "message-heading";
  if (message.role !== "user") heading.appendChild(document.createElement("i"));
  heading.appendChild(document.createTextNode(message.role === "user" ? "You" : "RobotInsight"));
  const content = document.createElement("div"); content.className = "message-content"; content.textContent = message.content;
  article.append(heading, content);
  if (message.role !== "user") {
    const copy = document.createElement("button"); copy.className = "copy-response";
    copy.textContent = "Copy response"; copy.setAttribute("aria-label", "Copy this response");
    copy.addEventListener("click", async () => {try {await navigator.clipboard.writeText(content.textContent); copy.textContent = "Copied"; setTimeout(() => copy.textContent = "Copy response", 1800);} catch {notice("Copy is unavailable. You can select the response text to copy it.");}});
    article.appendChild(copy);
  }
  $("messages").appendChild(article);
}
function renderMessages(messages) {
  const scroll = $("chat-scroll");
  const nearBottom = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 110;
  const prefixMatches = renderedMessages.every((m, i) => messages[i]?.role === m.role && messages[i]?.content === m.content);
  const last = renderedMessages.length - 1;
  const streamingTail = last >= 0 && messages.length >= renderedMessages.length && renderedMessages[last].role === "assistant" && messages[last]?.role === "assistant" && renderedMessages.slice(0, last).every((m, i) => messages[i]?.role === m.role && messages[i]?.content === m.content);
  if (!prefixMatches && streamingTail) {
    $("messages").children[last].querySelector(".message-content").textContent = messages[last].content;
  } else if (!prefixMatches) {$("messages").replaceChildren(); renderedMessages = [];}
  for (let i = renderedMessages.length; i < messages.length; i++) appendMessage(messages[i]);
  renderedMessages = messages.map(m => ({...m}));
  const latest = [...messages].reverse().find(message => message.role === "assistant");
  $("latest-response").textContent = latest?.content || "";
  $("latest-response").classList.toggle("hidden", !latest);
  if (latest && !chatOpen) $("unread").classList.remove("hidden");
  $("welcome").classList.toggle("hidden", messages.length > 0);
  if (messages.length && (nearBottom || messages.at(-1)?.role === "user")) scroll.scrollTo({top: scroll.scrollHeight, behavior: reducedMotion.matches ? "instant" : "smooth"});
}
async function poll() {
  try {
    const data = await api("/api/state");
    const reconnected = !connected;
    connected = true; preview = data.preview;
    if (reconnected && !preview) notice();
    $("connection").setAttribute("aria-label", preview ? "Preview connected" : "Assistant connected");
    $("connection").title = preview ? "Preview mode. Run the launcher to use the assistant." : "Assistant connected";
    $("connection").classList.remove("offline");
    updateState(data.state);
    const audioStatus = data.voice_status || {};
    if (preview) {
      $("presence-title").textContent = "Interface preview";
      $("presence-subtitle").textContent = "Start RobotInsight to enable voice input";
    }
    if (state === "idle" && !preview) {
      if (audioStatus.wakeword === "ready") {
        $("presence-subtitle").textContent = "Listening for “Hey In Site”";
      } else {
        $("presence-title").textContent = "Voice input needs attention";
        $("presence-subtitle").textContent = audioStatus.message || "Check your microphone in Devices";
      }
    }
    if (["idle", "listening"].includes(state) && audioStatus.wakeword !== "preview") {
      $("waveform").querySelectorAll("i").forEach((bar, index) => {
        bar.style.height = `${3 + (audioStatus.level || 0) * (14 + (index % 3) * 7)}px`;
      });
    }
    if (data.revision !== revision) {
      revision = data.revision;
      // Hold an accepted typed prompt on screen until the assistant consumes it.
      if (localEcho && data.messages.at(-1)?.content === localEcho) localEcho = null;
      if (data.messages.some(m => m.role === "user" && m.content === localEcho)) localEcho = null;
      renderMessages(localEcho ? [...data.messages, {role: "user", content: localEcho}] : data.messages);
    }
    voice = data.voice; $("voice-toggle").setAttribute("aria-pressed", String(voice));
    $("voice-toggle").querySelector("span").textContent = voice ? "Voice on" : "Voice off";
    $("camera-preview").classList.toggle("hidden", !data.capture);
    if (data.capture && $("camera-preview").querySelector("img").getAttribute("src") !== data.capture) $("camera-preview").querySelector("img").src = data.capture;
  } catch (error) {
    connected = false; updateControls();
    $("connection").setAttribute("aria-label", "Disconnected");
    $("connection").title = "Disconnected";
    $("connection").classList.add("offline");
    notice(error.message.includes("launcher") ? error.message : "Connection lost. Keep the assistant terminal open, or relaunch RobotInsight.");
  } finally {setTimeout(poll, 350);}
}
async function submitPrompt(text) {
  text = text.trim();
  if (!text || pending) return;
  pending = true; updateControls(); notice();
  try {
    await api("/api/prompt", {text});
    localEcho = text; renderMessages([...renderedMessages, {role: "user", content: text}]);
    $("prompt").value = "";
    // Avoid a double submission while the worker switches out of idle.
    await new Promise(resolve => setTimeout(resolve, 600));
  } catch (error) {notice(error.message);}
  finally {pending = false; updateControls();}
}
$("prompt-form").addEventListener("submit", event => {event.preventDefault(); if (!$("send").disabled) submitPrompt($("prompt").value);});
$("prompt").addEventListener("keydown", event => {if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {event.preventDefault(); $("prompt-form").requestSubmit();}});
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => submitPrompt(button.dataset.prompt)));
$("camera").addEventListener("click", () => submitPrompt("What do you see?"));
$("listen").addEventListener("click", async () => {pending = true; updateControls(); try {await api("/api/listen", {}); notice("Microphone activated. Go ahead and speak."); await new Promise(resolve => setTimeout(resolve, 600));} catch (error) {notice(error.message);} finally {pending = false; updateControls();}});
$("voice-toggle").addEventListener("click", async () => {try {await api("/api/voice", {enabled: !voice}); voice = !voice; $("voice-toggle").setAttribute("aria-pressed", String(voice)); $("voice-toggle").querySelector("span").textContent = voice ? "Voice on" : "Voice off";} catch (error) {notice(error.message);}});
function setChatOpen(open, focusInput = false) {
  chatOpen = open;
  $("conversation-panel").hidden = !open;
  document.body.classList.toggle("chat-open", open);
  $("chat-toggle").setAttribute("aria-expanded", String(open));
  if (open) {
    $("unread").classList.add("hidden");
    $("chat-scroll").scrollTop = $("chat-scroll").scrollHeight;
    if (focusInput) $("prompt").focus();
  } else $("chat-toggle").focus();
}
$("chat-toggle").addEventListener("click", () => setChatOpen(!chatOpen));
$("chat-close").addEventListener("click", () => setChatOpen(false));
$("type-message").addEventListener("click", () => setChatOpen(true, true));
$("examples-toggle").addEventListener("click", () => {
  const open = document.body.classList.toggle("examples-open");
  $("examples-toggle").setAttribute("aria-expanded", String(open));
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && chatOpen && !$("devices-dialog").open) setChatOpen(false);
});

function fillDeviceSelect(select, items, selected, fallback) {
  const choices = [new Option(fallback, "")];
  for (const item of items) choices.push(new Option(item.name, item.id));
  if (selected && !items.some(item => item.id === selected)) {
    const missing = new Option("Previously selected device — disconnected", selected);
    missing.disabled = true;
    choices.push(missing);
  }
  select.replaceChildren(...choices);
  select.value = selected || "";
}
function renderDevices(data) {
  fillDeviceSelect($("microphone-device"), data.microphones, data.selected.microphone, "System default microphone");
  fillDeviceSelect($("camera-device"), data.cameras, data.selected.camera, "Default camera");
  $("microphone-status").textContent = data.errors.microphone || (data.microphones.length ? "Used for the wake word and voice questions." : "No microphones detected. Connect one and refresh.");
  $("camera-status").textContent = data.errors.camera || (data.cameras.length ? "Used when you ask the robot to take a look." : "No cameras detected. Connect one and refresh.");
}
async function loadDevices() {
  if (deviceLoading) return;
  deviceLoading = true;
  $("devices-refresh").disabled = true;
  $("microphone-device").disabled = true;
  $("camera-device").disabled = true;
  $("device-feedback").classList.remove("error");
  $("device-feedback").textContent = "Detecting connected devices…";
  updateControls();
  try {
    renderDevices(await api("/api/devices"));
    $("device-feedback").textContent = "Choices are remembered on this computer.";
  } catch (error) {
    $("device-feedback").textContent = error.message;
    $("device-feedback").classList.add("error");
  } finally {
    deviceLoading = false;
    $("devices-refresh").disabled = false;
    $("microphone-device").disabled = false;
    $("camera-device").disabled = false;
    updateControls();
  }
}
$("devices-open").addEventListener("click", () => {$("devices-dialog").showModal(); loadDevices();});
$("devices-close").addEventListener("click", () => $("devices-dialog").close());
$("devices-refresh").addEventListener("click", loadDevices);
$("devices-dialog").addEventListener("click", event => {if (event.target === $("devices-dialog")) {const rect = event.target.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();}});
$("device-form").addEventListener("submit", async event => {
  event.preventDefault();
  deviceLoading = true; updateControls();
  $("device-feedback").classList.remove("error");
  try {
    const result = await api("/api/devices", {microphone: $("microphone-device").value, camera: $("camera-device").value});
    renderDevices(result);
    $("device-feedback").textContent = "Devices applied. Ready for your next question.";
  } catch (error) {
    $("device-feedback").classList.add("error");
    $("device-feedback").textContent = error.message;
  } finally {deviceLoading = false; updateControls();}
});
$("fullscreen").addEventListener("click", async () => {try {if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen();} catch {notice("Use F11 to toggle fullscreen in your browser.");}});
document.addEventListener("fullscreenchange", () => $("fullscreen").setAttribute("aria-label", document.fullscreenElement ? "Exit fullscreen" : "Enter fullscreen"));
$("robot-stage").addEventListener("pointermove", event => {const rect = $("robot-stage").getBoundingClientRect(); target = {x: (event.clientX - rect.left) / rect.width * 2 - 1, y: (event.clientY - rect.top) / rect.height * 2 - 1};});
$("robot-stage").addEventListener("pointerleave", () => target = {x: 0, y: 0});
function greet() {greetingUntil = performance.now() + 2400; $("hello-bubble").classList.add("show"); setTimeout(() => {if (performance.now() >= greetingUntil) $("hello-bubble").classList.remove("show");}, 2450);}
$("robot-stage").addEventListener("click", greet);
$("robot-stage").addEventListener("keydown", event => {if (["Enter", " "].includes(event.key)) {event.preventDefault(); greet();}});
const canvas = $("eyes"), ctx = canvas.getContext("2d");
function drawEye(cx, cy, openness, happy, t, side) {
  ctx.save(); ctx.translate(cx, cy); ctx.scale(1, openness);
  ctx.shadowColor = "#00d5ff"; ctx.shadowBlur = 26;
  const gradient = ctx.createLinearGradient(0, -40, 0, 35);
  gradient.addColorStop(0, "#35f7ef"); gradient.addColorStop(.5, "#08c8f6"); gradient.addColorStop(1, "#0877ed");
  ctx.fillStyle = gradient;
  ctx.beginPath();
  if (happy) {
    ctx.moveTo(-67, 19); ctx.bezierCurveTo(-58, -57, 51, -58, 67, 19);
    ctx.bezierCurveTo(33, 3, -31, 1, -67, 19);
  } else {
    ctx.roundRect(-48, -48, 96, 100, 38);
  }
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.save(); ctx.clip();
  ctx.fillStyle = "#002c7760";
  for (let y = -65; y < 60; y += 6) ctx.fillRect(-80, y, 160, 2);
  const shine = ctx.createLinearGradient(-65, 0, 65, 0); shine.addColorStop(0, "#ffffff00"); shine.addColorStop(.5, "#adffff45"); shine.addColorStop(1, "#ffffff00");
  ctx.fillStyle = shine; ctx.fillRect(-70, -54, 140, 110);
  ctx.restore(); ctx.restore();
}
let previousFrame = 0;
function animate(now) {
  requestAnimationFrame(animate);
  if (document.hidden || now - previousFrame < (reducedMotion.matches ? 180 : 32)) return;
  previousFrame = now;
  const t = now / 1000, motion = !reducedMotion.matches;
  gaze.x += (target.x - gaze.x) * .09; gaze.y += (target.y - gaze.y) * .09;
  const bob = motion ? Math.sin(t * 1.7) * 5 : 0;
  const tilt = motion ? gaze.x * 2 + Math.sin(t * .7) * .5 : 0;
  $("robot-float").style.transform = `translate(-50%, calc(-50% + ${bob}px)) rotate(${tilt}deg)`;
  ctx.clearRect(0, 0, 1000, 1000);
  const blinkCycle = t % 5.3;
  const blink = motion && blinkCycle > 5.08 ? Math.max(.06, Math.abs(blinkCycle - 5.19) / .11) : 1;
  const happy = state === "idle" || state === "speaking" || now < greetingUntil;
  let openness = blink;
  if (state === "warmup") openness *= .45;
  if (state === "speaking" && motion) openness *= .86 + Math.sin(t * 9) * .14;
  const dx = motion ? gaze.x * 15 + (state === "thinking" ? Math.sin(t * .9) * 9 : 0) : 0;
  const dy = motion ? gaze.y * 8 + (state === "thinking" ? -15 : 0) : 0;
  drawEye(375 + dx, 350 + dy, openness, happy, t, -1);
  drawEye(625 + dx, 350 + dy, openness, happy, t, 1);
  if (["thinking", "searching"].includes(state)) {
    for (let i=0;i<3;i++) {ctx.beginPath();ctx.fillStyle=`rgba(75,220,244,${motion ? .3 + .6 * (Math.sin(t * 3 - i) + 1) / 2 : .7})`;ctx.arc(475 + i * 25, 470, 4, 0, Math.PI*2);ctx.fill();}
  }
  if (state === "capturing") {
    ctx.strokeStyle="#6cfff1";ctx.lineWidth=3;ctx.shadowColor="#08cafa";ctx.shadowBlur=12;
    const y = 290 + (motion ? (Math.sin(t * 2)+1) * 80 : 80);ctx.beginPath();ctx.moveTo(300,y);ctx.lineTo(700,y);ctx.stroke();ctx.shadowBlur=0;
  }
}
updateControls(); poll(); requestAnimationFrame(animate);
