"use strict";
(() => {
  const data = document.getElementById("assignment-options");
  const area = document.getElementById("assign-area");
  const assignee = document.getElementById("assign-user");
  if (!data || !area || !assignee) return;
  const areas = JSON.parse(data.textContent);
  const refresh = () => {
    const previous = assignee.value;
    const selected = areas.find(item => String(item.id) === area.value);
    assignee.replaceChildren(new Option("Sin responsable", ""));
    for (const agent of selected?.agents || []) {
      assignee.add(new Option(agent.name, String(agent.id)));
    }
    if (Array.from(assignee.options).some(item => item.value === previous)) {
      assignee.value = previous;
    }
  };
  area.addEventListener("change", refresh);
  refresh();
})();
