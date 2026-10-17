(() => {
  "use strict";

  const content = document.getElementById("chapter-content");
  if (!content) return;

  const panels = [...content.querySelectorAll(".view-panel[data-panel]")];
  const viewButtons = [...document.querySelectorAll("button[data-view-choice]")];
  const fullPanel = panels.find(panel => panel.dataset.panel === "full");
  const sections = fullPanel ? [...fullPanel.querySelectorAll(".note-section")] : [];
  const readingLocations = fullPanel ? [...fullPanel.querySelectorAll(".note-section, .term-index")] : [];
  const tools = document.getElementById("reading-tools");
  const contents = document.getElementById("chapter-contents");
  const navigation = document.getElementById("chapter-nav");
  const sidebar = navigation?.closest(".sidebar");
  const search = document.getElementById("chapter-search");
  const searchStatus = document.getElementById("search-status");
  const initialStatus = searchStatus?.textContent.trim() || "输入关键词筛选本章小节；清空搜索可恢复全文。";
  const hintButtons = [...content.querySelectorAll("button[data-reveal-hint]")];
  const hintLabels = new Map(hintButtons.map(button => [button, button.textContent]));
  const initiallyDisabled = new Map(hintButtons.map(button => [button, button.disabled]));
  const mobileLayout = window.matchMedia("(max-width: 48rem)");
  const printMedia = window.matchMedia("print");
  let printSnapshot = null;
  let locationObserver = null;
  let observedHeight = 0;
  let locationFrame = 0;

  const normalize = value => value.normalize("NFKC").toLocaleLowerCase().replace(/\s+/g, " ").trim();
  const searchIndex = new Map(sections.map(section => [
    section,
    normalize(`${section.textContent} ${section.dataset.searchAliases || ""}`)
  ]));

  function hintsFor(button) {
    const task = button.closest(".recall-task");
    return task ? [...task.querySelectorAll(".hint")] : [];
  }

  hintButtons.forEach((button, index) => {
    const hints = hintsFor(button);
    hints.forEach((hint, number) => {
      if (!hint.id) hint.id = `recall-hint-${index + 1}-${number + 1}`;
    });
    button.setAttribute("aria-controls", hints.map(hint => hint.id).join(" "));
    button.setAttribute("aria-expanded", String(hints.some(hint => !hint.hidden)));
  });
  navigation?.querySelectorAll("a[data-recall-label]").forEach(link => {
    link.dataset.fullTitle = link.textContent;
  });

  panels.forEach(panel => {
    if (!panel.id) panel.id = `view-${panel.dataset.panel}`;
    viewButtons.filter(button => button.dataset.viewChoice === panel.dataset.panel)
      .forEach(button => button.setAttribute("aria-controls", panel.id));
  });

  function resetRecall() {
    content.querySelectorAll(".recall-task details.answer").forEach(answer => { answer.open = false; });
    content.querySelectorAll(".recall-task .hint").forEach(hint => { hint.hidden = true; });
    hintButtons.forEach(button => {
      button.disabled = initiallyDisabled.get(button);
      button.textContent = hintLabels.get(button);
      button.setAttribute("aria-expanded", "false");
    });
  }

  function setView(choice) {
    const next = panels.some(panel => panel.dataset.panel === choice) ? choice : "full";
    if (next === "recall" && document.body.dataset.view !== "recall") resetRecall();
    panels.forEach(panel => { panel.hidden = panel.dataset.panel !== next; });
    viewButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.viewChoice === next)));
    document.body.dataset.view = next;
    navigation?.querySelectorAll("a[data-recall-label]").forEach(link => {
      link.textContent = next === "recall" ? link.dataset.recallLabel : link.dataset.fullTitle;
    });
    if (next !== "full") markLocation("");
    else queueLocationRefresh();
  }

  function markLocation(id) {
    let activeLink = null;
    let changed = false;
    navigation?.querySelectorAll("a[href^='#']").forEach(link => {
      if (link.getAttribute("href") === `#${id}`) {
        changed = link.getAttribute("aria-current") !== "location";
        link.setAttribute("aria-current", "location");
        activeLink = link;
      } else link.removeAttribute("aria-current");
    });
    if (!changed || !activeLink || !sidebar || mobileLayout.matches || !contents?.open) return;
    const container = sidebar.getBoundingClientRect();
    const link = activeLink.getBoundingClientRect();
    // Move only the contents pane; passive reading must not move the document.
    if (link.top < container.top) sidebar.scrollTop += link.top - container.top;
    else if (link.bottom > container.bottom) sidebar.scrollTop += link.bottom - container.bottom;
  }

  function queueLocationRefresh() {
    if (printSnapshot || printMedia.matches || locationFrame) return;
    locationFrame = window.requestAnimationFrame(() => {
      locationFrame = 0;
      if (printSnapshot || printMedia.matches) return;
      const height = Math.max(2, window.innerHeight);
      const readingLine = Math.max(1, Math.min(120, Math.round(height * .2)));
      if (typeof window.IntersectionObserver === "function" && (!locationObserver || height !== observedHeight)) {
        locationObserver?.disconnect();
        observedHeight = height;
        // A narrow reading line tracks even sections taller than the viewport.
        locationObserver = new IntersectionObserver(queueLocationRefresh, {
          rootMargin: `-${readingLine}px 0px -${Math.max(0, height - readingLine - 1)}px 0px`,
          threshold: 0
        });
        readingLocations.forEach(section => locationObserver.observe(section));
      }
      if (document.body.dataset.view !== "full") {
        markLocation("");
        return;
      }
      const visible = readingLocations.filter(section => !section.hidden);
      let current = visible[0];
      for (const section of visible) {
        if (section.getBoundingClientRect().top <= readingLine) current = section;
        else break;
      }
      markLocation(current?.id || "");
    });
  }

  function filterSections() {
    const query = normalize(search?.value || "");
    const terms = query.split(" ").filter(Boolean);
    let matches = 0;
    sections.forEach(section => {
      const matched = terms.every(term => searchIndex.get(section).includes(term));
      section.hidden = !matched;
      if (matched) matches += 1;
    });
    if (searchStatus) {
      searchStatus.textContent = !query ? initialStatus : matches
        ? `找到 ${matches} / ${sections.length} 个相关小节。清空搜索可恢复全文。`
        : "没有找到匹配小节。请换一个关键词，或清空搜索恢复全文。";
    }
    const glossary = fullPanel?.querySelector(".term-index");
    if (glossary) glossary.hidden = Boolean(query);
    if (query) markLocation("");
    queueLocationRefresh();
  }

  function clearSearch() {
    if (search) search.value = "";
    filterSections();
  }

  function openSection(id, updateHash = true) {
    const section = sections.find(item => item.id === id);
    if (!section) return;
    clearSearch();
    setView("full");
    if (mobileLayout.matches && contents) contents.open = false;
    markLocation(id);
    const heading = section.querySelector("h2, h3") || section;
    if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
    section.scrollIntoView({ block: "start", behavior: "auto" });
    if (updateHash) {
      try { window.history.replaceState(null, "", `#${encodeURIComponent(id)}`); }
      catch { /* Reading still works when the host disallows history changes. */ }
    }
  }

  function noteTarget(id) {
    const target = document.getElementById(id);
    if (!target || !fullPanel?.contains(target)) return null;
    return id === "note-terms" || target.matches(".numbered-equation, .term-index tr[id]") ? target : null;
  }

  function openNoteTarget(id, updateHash = true) {
    const target = noteTarget(id);
    if (!target) return;
    clearSearch();
    setView("full");
    for (let ancestor = target.parentElement; ancestor && ancestor !== fullPanel; ancestor = ancestor.parentElement) {
      if (ancestor.tagName === "DETAILS") ancestor.open = true;
    }
    if (target.id === "note-terms") target.querySelector("details")?.setAttribute("open", "");
    if (mobileLayout.matches && contents) contents.open = false;
    if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "start", behavior: "auto" });
    queueLocationRefresh();
    if (updateHash) {
      try { window.history.replaceState(null, "", `#${encodeURIComponent(id)}`); }
      catch { /* Reading still works when the host disallows history changes. */ }
    }
  }

  viewButtons.forEach(button => button.addEventListener("click", () => setView(button.dataset.viewChoice)));
  search?.addEventListener("input", () => {
    setView("full");
    filterSections();
  });

  navigation?.addEventListener("click", event => {
    const link = event.target.closest("a[href^='#']");
    if (!link || !navigation.contains(link) || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const id = link.getAttribute("href").slice(1);
    if (!sections.some(section => section.id === id)) return;
    event.preventDefault();
    openSection(id);
  });

  document.querySelectorAll("a[data-open-section]").forEach(link => link.addEventListener("click", event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const id = link.dataset.openSection;
    if (!sections.some(section => section.id === id)) return;
    event.preventDefault();
    openSection(id);
  }));

  document.addEventListener("click", event => {
    const link = event.target.closest("a[data-note-target]");
    if (!link || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const id = link.dataset.noteTarget;
    if (!noteTarget(id)) return;
    event.preventDefault();
    openNoteTarget(id);
  });

  hintButtons.forEach(button => button.addEventListener("click", () => {
    const hints = hintsFor(button);
    const nextHint = hints.find(hint => hint.hidden);
    if (!nextHint) return;
    nextHint.hidden = false;
    const complete = hints.every(hint => !hint.hidden);
    button.disabled = complete;
    button.textContent = complete ? "已显示全部提示" : "再看一条提示";
    button.setAttribute("aria-expanded", "true");
  }));

  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k" && search) {
      event.preventDefault();
      if (tools) tools.open = true;
      search.focus();
    }
  });

  function applyLayoutDefaults() {
    if (contents) contents.open = !mobileLayout.matches;
    if (mobileLayout.matches && tools) tools.open = false;
    queueLocationRefresh();
  }
  if (tools) tools.open = false;
  applyLayoutDefaults();
  if (mobileLayout.addEventListener) mobileLayout.addEventListener("change", applyLayoutDefaults);
  else mobileLayout.addListener(applyLayoutDefaults);

  function preparePrint() {
    if (printSnapshot) return;
    const disclosures = fullPanel ? [...fullPanel.querySelectorAll("details")] : [];
    printSnapshot = {
      view: document.body.dataset.view,
      panels: panels.map(panel => [panel, panel.hidden]),
      sections: readingLocations.map(section => [section, section.hidden]),
      disclosures: disclosures.map(detail => [detail, detail.open]),
      buttons: viewButtons.map(button => [button, button.getAttribute("aria-pressed")])
    };
    document.body.dataset.view = "full";
    panels.forEach(panel => { panel.hidden = panel.dataset.panel !== "full"; });
    readingLocations.forEach(section => { section.hidden = false; });
    disclosures.forEach(detail => { detail.open = true; });
    viewButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.viewChoice === "full")));
  }

  function restoreAfterPrint() {
    if (!printSnapshot) return;
    const saved = printSnapshot;
    printSnapshot = null;
    document.body.dataset.view = saved.view;
    saved.panels.forEach(([panel, hidden]) => { panel.hidden = hidden; });
    saved.sections.forEach(([section, hidden]) => { section.hidden = hidden; });
    saved.disclosures.forEach(([detail, open]) => { detail.open = open; });
    saved.buttons.forEach(([button, pressed]) => {
      if (pressed === null) button.removeAttribute("aria-pressed");
      else button.setAttribute("aria-pressed", pressed);
    });
  }

  document.getElementById("print-notes")?.addEventListener("click", () => window.print());
  window.addEventListener("beforeprint", preparePrint);
  window.addEventListener("afterprint", restoreAfterPrint);
  const printChange = event => event.matches ? preparePrint() : restoreAfterPrint();
  if (printMedia.addEventListener) printMedia.addEventListener("change", printChange);
  else printMedia.addListener(printChange);

  function followCurrentHash() {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); }
    catch { return; }
    if (sections.some(section => section.id === id)) openSection(id, false);
    else if (noteTarget(id)) openNoteTarget(id, false);
  }
  window.addEventListener("hashchange", followCurrentHash);
  window.addEventListener("resize", queueLocationRefresh);
  window.addEventListener("load", queueLocationRefresh);
  document.addEventListener("toggle", queueLocationRefresh, true);
  setView(document.body.dataset.view || "full");
  filterSections();
  if (window.location.hash) window.requestAnimationFrame(followCurrentHash);
})();
