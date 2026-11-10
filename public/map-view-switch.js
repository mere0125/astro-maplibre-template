(() => {
  const setup = async () => {
    const mapElement = document.getElementById("temporary-forest-map");
    if (!mapElement || mapElement.dataset.viewSwitchReady === "true") return;
    mapElement.dataset.viewSwitchReady = "true";

    await customElements.whenDefined("ml-map");
    await mapElement.mapReady();
    const map = mapElement.getMap();
    const buttons = [...document.querySelectorAll("[data-map-view]")];
    const compact = window.innerWidth < 640;
    if (compact) document.querySelector(".map-key")?.removeAttribute("open");
    const show = (view) => {
      buttons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.mapView === view)));
      if (view === "study") {
        map.fitBounds(
          [[-73.8990, 40.6632], [-73.8716, 40.6774]],
          { padding: compact ? { top: 235, right: 28, bottom: 170, left: 28 } : { top: 55, right: 70, bottom: 70, left: 365 }, duration: 1300 }
        );
      } else {
        map.fitBounds(
          [[-74.267, 40.489], [-73.680, 40.932]],
          { padding: compact ? { top: 235, right: 20, bottom: 145, left: 20 } : { top: 45, right: 55, bottom: 55, left: 360 }, duration: 1300 }
        );
      }
    };

    buttons.forEach((button) => button.addEventListener("click", () => show(button.dataset.mapView)));
  };

  setup();
  document.addEventListener("astro:page-load", setup);
})();
