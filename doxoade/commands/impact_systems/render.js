const graphDiv = document.getElementById("graph");

let mermaidGraph = "graph TD\n";

DATA.edges.forEach(e => {
  mermaidGraph += `"${e.source}" --> "${e.target}"\n`;
});

graphDiv.innerHTML = `<pre class="mermaid">${mermaidGraph}</pre>`;

mermaid.initialize({ startOnLoad: true });

// ALERTS
const alertsDiv = document.getElementById("alerts");

DATA.alerts.forEach(a => {
  const el = document.createElement("div");
  el.className = "cycle";

  el.innerText =
    `[${a.severity}] ${a.path.join(" → ")}`;

  alertsDiv.appendChild(el);
});