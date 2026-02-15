let seconds = 15;
let interval;

function startTimer() {
  if (interval) return;

  interval = setInterval(() => {
    seconds--;

    document.getElementById("time").textContent =
      Math.floor(seconds / 60) + ":" + (seconds % 60).toString().padStart(2, "0");

    if (seconds <= 0) {
      clearInterval(interval);
      interval = null;
      alert("Focus session complete!");
      logSession(25);
    }
  }, 1000);
}

function resetTimer() {
  clearInterval(interval);
  interval = null;
  seconds = 1500;
  document.getElementById("time").textContent = "25:00";
}

function logSession(minutes) {
  fetch("/log_session", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: "minutes=" + minutes
  });
}
