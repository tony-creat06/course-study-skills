const topics = Array.from(document.querySelectorAll('article.topic'));
const explanations = Array.from(document.querySelectorAll('details.explanation'));
const contents = document.querySelector('#contents');
const search = document.querySelector('#note-search');
const findTools = document.querySelector('#find-tools');
const searchStatus = document.querySelector('#search-status');
const readButton = document.querySelector('#reading-mode');
const recallButton = document.querySelector('#recall-mode');
let printState = null;

function resetHints() {
  topics.forEach(topic => {
    topic.querySelectorAll('.hint-panel').forEach(panel => panel.hidden = true);
    const button = topic.querySelector('.hint-reveal');
    if (button) {
      button.disabled = false;
      button.textContent = '看一条提示';
    }
  });
}

function setMode(mode) {
  if (document.body.dataset.mode === mode) return;
  document.body.dataset.mode = mode;
  readButton.setAttribute('aria-pressed', String(mode === 'reading'));
  recallButton.setAttribute('aria-pressed', String(mode === 'recall'));
  explanations.forEach(detail => detail.open = false);
  topics.forEach(topic => {
    const hints = topic.querySelector('.hint-set');
    if (hints) hints.hidden = mode !== 'recall';
  });
  resetHints();
}

function filterTopics() {
  const terms = search.value.normalize('NFKC').toLowerCase().trim().split(/\s+/).filter(Boolean);
  let count = 0;
  topics.forEach(topic => {
    const haystack = topic.dataset.search;
    topic.hidden = !terms.every(term => haystack.includes(term));
    if (!topic.hidden) count += 1;
  });
  searchStatus.textContent = terms.length ? (count ? `找到 ${count} 个主题` : '没有匹配的主题。试试中文名、英文名或相关词。') : '';
}

readButton.addEventListener('click', () => setMode('reading'));
recallButton.addEventListener('click', () => setMode('recall'));
document.querySelector('#expand').addEventListener('click', () => explanations.forEach(detail => detail.open = true));
document.querySelector('#collapse').addEventListener('click', () => explanations.forEach(detail => detail.open = false));
document.querySelector('#print').addEventListener('click', () => window.print());
search.addEventListener('input', filterTopics);
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault(); findTools.open = true; search.focus();
  }
});

topics.forEach(topic => {
  topic.dataset.search = ((topic.dataset.aliases || '') + ' ' + topic.textContent).normalize('NFKC').toLowerCase();
  const reveal = topic.querySelector('.hint-reveal');
  if (reveal) reveal.addEventListener('click', () => {
    const panels = Array.from(topic.querySelectorAll('.hint-panel'));
    const next = panels.find(panel => panel.hidden);
    if (next) next.hidden = false;
    if (panels.every(panel => !panel.hidden)) {
      reveal.disabled = true; reveal.textContent = '提示已全部显示';
    }
  });
});

document.querySelectorAll('a[href^="#topic-"]').forEach(link => link.addEventListener('click', () => {
  search.value = ''; filterTopics();
  if (matchMedia('(max-width: 860px)').matches) contents.open = false;
}));

const narrow = matchMedia('(max-width: 860px)');
function adaptContents() {
  contents.open = !narrow.matches;
  findTools.open = !narrow.matches;
}
narrow.addEventListener('change', adaptContents);
adaptContents();

window.addEventListener('beforeprint', () => {
  if (printState === null) printState = {
    mode: document.body.dataset.mode,
    explanations: explanations.map(detail => detail.open),
    topics: topics.map(topic => topic.hidden),
    hintSets: topics.map(topic => topic.querySelector('.hint-set')?.hidden ?? null)
  };
  document.body.dataset.mode = 'reading';
  topics.forEach(topic => topic.hidden = false);
  explanations.forEach(detail => detail.open = true);
});
window.addEventListener('afterprint', () => {
  if (printState === null) return;
  document.body.dataset.mode = printState.mode;
  explanations.forEach((detail, index) => detail.open = printState.explanations[index]);
  topics.forEach((topic, index) => {
    topic.hidden = printState.topics[index];
    const hints = topic.querySelector('.hint-set');
    if (hints && printState.hintSets[index] !== null) hints.hidden = printState.hintSets[index];
  });
  printState = null;
});
