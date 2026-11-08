// {{TITLE}}: the build work order fills this in. Failures show a message instead of a blank screen.
const errorBox = document.getElementById('error');
function showError(message) { errorBox.textContent = `Something went wrong: ${message}. Reload to try again.`; errorBox.hidden = false; }
addEventListener('error', (e) => showError(e.message || 'an unexpected error'));
addEventListener('unhandledrejection', (e) => showError((e.reason && e.reason.message) || 'a request failed'));

function render() {
  document.getElementById('content').textContent = 'Ready.';
}
render();
