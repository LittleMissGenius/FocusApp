let totalTime = 25 * 60; // 25 minutes
let time = totalTime;
let interval = null;

function updateDisplay() {
  let minutes = Math.floor(time / 60);
  let seconds = time % 60;
  document.getElementById("timer-display").innerText =
    `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function startTimer() {
  if (interval) return;

  interval = setInterval(() => {
    if (time > 0) {
      time--;
      updateDisplay();
    } else {
      clearInterval(interval);
      interval = null;

      fetch("/log_session", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: "minutes=25"
      });

      alert("Session complete! 🌱");
      resetTimer();
    }
  }, 1000);
}

function stopTimer() {
  clearInterval(interval);
  interval = null;
}

function resetTimer() {
  stopTimer();
  time = totalTime;
  updateDisplay();
}

updateDisplay();

function logSession(minutes) {
  fetch("/log_session", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: "minutes=" + minutes
  });
}
