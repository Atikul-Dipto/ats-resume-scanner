// Signed-out users' assistant memories stay in this browser.
const KEY = "prottoy-assistant-memories";
const MAX = 30;

export function loadLocalMemories() {
  try {
    const list = JSON.parse(window.localStorage.getItem(KEY));
    return Array.isArray(list) ? list.filter((m) => typeof m === "string") : [];
  } catch {
    return [];
  }
}

export function saveLocalMemories(list) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list.slice(-MAX)));
  } catch {
    /* storage unavailable */
  }
}

export function addLocalMemory(fact) {
  const list = loadLocalMemories().filter((m) => m !== fact);
  saveLocalMemories([...list, fact]);
}
