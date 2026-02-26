let totalTime = 25 * 60;  // default work time
let time = totalTime;
let interval = null;
let currentMode = "work";

// Update timer display
function updateDisplay() {
  let minutes = Math.floor(time / 60);
  let seconds = time % 60;
  document.getElementById("timer-display").innerText =
    `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

// Start timer
function startTimer(mode) {
  stopTimer(); // stop current timer if running
  currentMode = mode;

  // Read custom values
  const workInput = document.getElementById("work-time").value;
  const breakInput = document.getElementById("break-time").value;

  if (mode === "work") {
    totalTime = parseInt(workInput) * 60;
  } else if (mode === "break") {
    totalTime = parseInt(breakInput) * 60;
  }

  time = totalTime;
  updateDisplay();

  interval = setInterval(() => {
    if (time > 0) {
      time--;
      updateDisplay();
    } else {
      clearInterval(interval);
      interval = null;

      // Log session only for work timer
      if (currentMode === "work") {
        fetch("/log_session", {
          method: "POST",
          headers: {"Content-Type": "application/x-www-form-urlencoded"},
          body: "minutes=" + parseInt(workInput)
        });
        alert("Work session complete! 🌱");
      } else {
        alert("Break over! ☕");
      }

      resetTimer(); // reset display after finishing
    }
  }, 1000);
}

// Stop timer
function stopTimer() {
  clearInterval(interval);
  interval = null;
}

// Reset timer
function resetTimer() {
  stopTimer();
  const workInput = document.getElementById("work-time").value;
  time = currentMode === "work" ? parseInt(workInput) * 60 : parseInt(document.getElementById("break-time").value) * 60;
  updateDisplay();
}

// Initialize display on load
updateDisplay();
