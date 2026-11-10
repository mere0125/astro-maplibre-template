import {
  Map as MapLibreMap,
  ScaleControl,
  AttributionControl,
  setWorkerUrl,
  type FilterSpecification,
  type LngLatBoundsLike,
  type StyleSpecification,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from "geojson";

type Parcel = {
  bbl: string;
  address: string;
  sample_id: number;
  lotarea: number;
  condition_1996: string;
  condition_2018: string;
  confidence_1996: string;
  confidence_2018: string;
  history_group: "open_in_both" | "built_then_open";
  history_label: string;
  history_color: string;
  vegetation_color: string;
  veg_pct: number;
  veg_class: number;
  ndvi_mean: number;
  ndvi_median: number;
  pixel_count: number;
};
type ParcelFeature = Feature<Polygon | MultiPolygon, Parcel>;
type Manifest = {
  counts: Record<string, number>;
  boroughs: Array<{ code: string; name: string; records: number; mapped: number; bounds?: number[] }>;
  bounds: { citywide: number[]; screening: number[]; sample: number[] };
  images: Record<string, Record<string, string>>;
};

const root = document.getElementById("field-index");
const element = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

if (root) {
  const base = root.dataset.base || "/";
  const asset = (path: string) => `${base.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
  const json = async <T>(path: string): Promise<T> => {
    const response = await fetch(asset(path));
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return response.json() as Promise<T>;
  };
  const showError = (message: string) => {
    element("map-loading").hidden = true;
    element("map-status").textContent = message;
    element("map-status").hidden = false;
  };

  const start = async () => {
    const [manifest, parcels, screening, basemap] = await Promise.all([
      json<Manifest>("data/assignment04/manifest.json"),
      json<FeatureCollection<Polygon | MultiPolygon, Parcel>>("data/assignment04/parcels.geojson"),
      json<FeatureCollection>("data/assignment04/screening.geojson"),
      json<StyleSpecification>("style.json"),
    ]);

    // The analytical layers keep their own precise colours. The basemap is
    // quieter because it locates the parcels rather than supplying evidence.
    for (const layer of basemap.layers) {
      if (layer.type === "background") layer.paint = { "background-color": "#f2f0e6" };
      if (layer.id === "water" && layer.type === "fill") layer.paint = { ...layer.paint, "fill-color": "#dce6df" };
      if (layer.id === "park" && layer.type === "fill") layer.paint = { ...layer.paint, "fill-color": "#e3ead8" };
      if (layer.id === "building" && layer.type === "fill") layer.paint = { ...layer.paint, "fill-color": "#e6e0d3", "fill-outline-color": "#ded8ca", "fill-opacity": 0.62 };
      if (layer.type === "symbol" && layer.id.startsWith("highway_name")) {
        layer.paint = { ...layer.paint, "text-opacity": 0.47, "text-color": "#7f8b74" };
      }
    }

    setWorkerUrl(workerUrl);
    const map = new MapLibreMap({
      container: "assignment-map",
      style: basemap,
      center: [-73.98, 40.705],
      zoom: 9.6,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
      minZoom: 8,
      maxZoom: 19,
      renderWorldCopies: false,
    });
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new AttributionControl({ compact: true }), "bottom-right");
    map.addControl(new ScaleControl({ maxWidth: 130, unit: "imperial" }), "bottom-left");

    const state = {
      scale: "city" as "city" | "study",
      reading: "vegetation" as "vegetation" | "history",
      history: "all",
      vegetation: "all",
      selected: null as string | null,
      evidence: "archive" as "archive" | "2022",
      borough: "all",
      ready: false,
    };
    const features = parcels.features as ParcelFeature[];
    const byBBL = new globalThis.Map(features.map((feature) => [feature.properties.bbl, feature]));
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cityLayers = ["a4-city-fill", "a4-city-edge"];
    const studyLayers = ["a4-screening", "a4-screening-edge", "a4-parcels", "a4-parcel-edge", "a4-selected-halo", "a4-selected-edge"];
    const compact = () => window.innerWidth <= 760;
    let imageRequest = 0;
    const duration = (value: number) => reducedMotion ? 0 : value;
    const fit = (bounds: number[], selected = false) => {
      const mapWidth = map.getContainer().clientWidth;
      const small = compact() || mapWidth < 700;
      const evidencePadding = Math.min(mapWidth - 120, element("parcel-sheet").offsetWidth + (window.innerWidth <= 1100 ? 60 : 72) + 20);
      const padding = selected
        ? compact() ? { top: 70, bottom: 50, left: 28, right: 28 } : { top: 95, bottom: 80, left: small ? 26 : 90, right: evidencePadding }
        : small ? { top: 90, bottom: 110, left: 26, right: 45 } : { top: 100, bottom: 85, left: 85, right: 100 };
      map.fitBounds(bounds as LngLatBoundsLike, { padding, duration: duration(1050), maxZoom: selected ? 17.3 : state.scale === "city" ? 12.3 : 15.2 });
    };
    const matches = (feature: ParcelFeature) =>
      (state.history === "all" || feature.properties.history_group === state.history) &&
      (state.vegetation === "all" || feature.properties.veg_class === Number(state.vegetation));

    const titleCase = (value: string) => value.toLowerCase().replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
    const valueText = (value: number) => value.toFixed(1);
    const filterExpression = (): FilterSpecification => {
      const parts: FilterSpecification[] = [];
      if (state.history !== "all") parts.push(["==", ["get", "history_group"], state.history]);
      if (state.vegetation !== "all") parts.push(["==", ["get", "veg_class"], Number(state.vegetation)]);
      return parts.length ? ["all", ...parts] as FilterSpecification : ["has", "bbl"];
    };

    const imageComparison = () => {
      const split = Number(element<HTMLInputElement>("image-comparison").value);
      element("image-front").style.clipPath = `inset(0 ${100 - split}% 0 0)`;
      element("image-seam").style.left = `${split}%`;
      element("image-label-left").hidden = split < 8;
      element("image-label-right").hidden = split > 92;
    };

    const updateImages = () => {
      if (!state.selected) return;
      const images = manifest.images[state.selected];
      if (!images) return;
      const archive = state.evidence === "archive";
      const request = ++imageRequest;
      const frontPath = archive ? images["1996"] : images["2022_rgb"];
      const backPath = archive ? images["2018"] : images["2022_ndvi"];
      const address = titleCase(byBBL.get(state.selected)!.properties.address);
      const front = element<HTMLImageElement>("image-front-img");
      const back = element<HTMLImageElement>("image-back");
      front.style.opacity = "0";
      back.style.opacity = "0";
      element("image-loading").hidden = false;
      front.src = asset(frontPath);
      back.src = asset(backPath);
      front.alt = `${address} - ${archive ? "1996 aerial photography" : "2022 true-colour aerial imagery"}`;
      back.alt = `${address} - ${archive ? "2018 orthophotography" : "2022 per-pixel NDVI"}`;
      element("image-label-left").textContent = archive ? "1996" : "2022 - aerial image";
      element("image-label-right").textContent = archive ? "2018" : "2022 - pixel NDVI";
      element("image-caption").textContent = archive
        ? "Slide across the same 450-foot ground context. The pale outline traces the current parcel. The two dates are snapshots, not a continuous record."
        : "The same 2022 ground extent, shown as a true-colour image and pixel NDVI. The NDVI display is clamped at −0.2 and 0.8; this does not change the measurements.";
      element("pixel-key").hidden = archive;
      element<HTMLInputElement>("image-comparison").setAttribute("aria-label", archive ? "Compare 1996 and 2018 aerial imagery" : "Compare 2022 true-colour imagery and pixel NDVI");
      document.querySelectorAll<HTMLButtonElement>("[data-evidence]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.evidence === state.evidence)));
      imageComparison();
      Promise.all([front.decode(), back.decode()]).then(() => {
        if (request !== imageRequest) return;
        front.style.opacity = "1";
        back.style.opacity = "1";
        element("image-loading").hidden = true;
      }).catch(() => {
        if (request === imageRequest) element("image-loading").textContent = "The dated image could not load. Choose the parcel again to retry.";
      });
    };

    const closeParcel = () => {
      state.selected = null;
      element("parcel-sheet").hidden = true;
      root.classList.remove("has-parcel");
      if (state.ready) {
        map.setFilter("a4-selected-halo", ["==", ["get", "bbl"], ""]);
        map.setFilter("a4-selected-edge", ["==", ["get", "bbl"], ""]);
      }
      document.querySelectorAll<HTMLButtonElement>(".parcel-choice").forEach((button) => button.setAttribute("aria-pressed", "false"));
    };

    const boundsOf = (feature: ParcelFeature): number[] => {
      const coordinates = feature.geometry.coordinates.flat(feature.geometry.type === "MultiPolygon" ? 2 : 1) as Position[];
      return [Math.min(...coordinates.map((coordinate) => coordinate[0])), Math.min(...coordinates.map((coordinate) => coordinate[1])), Math.max(...coordinates.map((coordinate) => coordinate[0])), Math.max(...coordinates.map((coordinate) => coordinate[1]))];
    };

    const selectParcel = (bbl: string) => {
      const feature = byBBL.get(bbl);
      if (!feature || !matches(feature) || state.scale !== "study") return;
      const p = feature.properties;
      state.selected = bbl;
      state.evidence = "archive";
      element("parcel-address").textContent = titleCase(p.address);
      element("parcel-identification").textContent = `BBL ${p.bbl} - ${Math.round(p.lotarea)} square feet`;
      element("status-1996").textContent = p.condition_1996 === "open ground" ? "open ground" : "building visible";
      element("status-2018").textContent = p.condition_2018 === "open ground" ? "open ground" : "building visible";
      element("vegetation-value").textContent = `${valueText(p.veg_pct)}%`;
      element("response-fill").style.width = `${p.veg_pct}%`;
      element("response-detail").textContent = `Mean NDVI ${p.ndvi_mean.toFixed(3)} - ${p.pixel_count} valid pixels`;
      element<HTMLInputElement>("image-comparison").value = "50";
      updateImages();
      element("parcel-sheet").hidden = false;
      root.classList.add("has-parcel");
      if (window.innerWidth <= 1100) {
        element("atlas-map-key").hidden = true;
        element("toggle-legend").setAttribute("aria-expanded", "false");
      }
      map.setFilter("a4-selected-halo", ["==", ["get", "bbl"], bbl]);
      map.setFilter("a4-selected-edge", ["==", ["get", "bbl"], bbl]);
      document.querySelectorAll<HTMLButtonElement>(".parcel-choice").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.bbl === bbl)));
      // A minimum context makes comparison possible even for very narrow lots.
      const bounds = boundsOf(feature);
      const centerX = (bounds[0] + bounds[2]) / 2;
      const centerY = (bounds[1] + bounds[3]) / 2;
      fit([centerX - 0.0016, centerY - 0.0012, centerX + 0.0016, centerY + 0.0012], true);
    };

    const renderList = (fitResults = false) => {
      const filtered = features.filter(matches).sort((a, b) => b.properties.veg_pct - a.properties.veg_pct);
      const list = element("parcel-list");
      list.replaceChildren();
      for (const feature of filtered) {
        const p = feature.properties;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "parcel-choice";
        button.dataset.bbl = p.bbl;
        button.setAttribute("aria-pressed", String(state.selected === p.bbl));
        button.setAttribute("aria-label", `${titleCase(p.address)}, ${valueText(p.veg_pct)} percent vegetation response, ${p.history_label}`);
        const label = document.createElement("span");
        const swatch = document.createElement("i");
        swatch.setAttribute("aria-hidden", "true");
        swatch.style.setProperty("--history-colour", p.history_color);
        swatch.style.setProperty("--vegetation-colour", p.vegetation_color);
        label.append(swatch, document.createTextNode(titleCase(p.address)));
        const value = document.createElement("span");
        value.textContent = `${valueText(p.veg_pct)}%`;
        button.append(label, value);
        button.addEventListener("click", () => selectParcel(p.bbl));
        list.append(button);
      }
      element("sample-count").textContent = `${filtered.length} of 14 parcels`;
      element("no-parcels").hidden = filtered.length > 0;
      if (state.selected && !filtered.some((feature) => feature.properties.bbl === state.selected)) closeParcel();
      if (state.ready) {
        const filter = filterExpression();
        map.setFilter("a4-parcels", filter);
        map.setFilter("a4-parcel-edge", filter);
        if (state.scale === "study" && fitResults) {
          const bounds = filtered.map(boundsOf);
          fit(bounds.length
            ? [Math.min(...bounds.map((b) => b[0])), Math.min(...bounds.map((b) => b[1])), Math.max(...bounds.map((b) => b[2])), Math.max(...bounds.map((b) => b[3]))]
            : manifest.bounds.screening);
        }
      }
      if (state.scale === "study") element("caption-detail").textContent = `${filtered.length} of 14 sampled lots - ${state.reading === "vegetation" ? "2022 spectral vegetation response" : "1996 and 2018 image readings"}`;
    };

    const updateReading = () => {
      element("vegetation-key").hidden = state.reading !== "vegetation";
      element("key-title").textContent = state.scale === "city" ? "vacant land records" : state.reading === "vegetation" ? "the 2022 response" : "two historical readings";
      if (!state.ready) return;
      map.setPaintProperty("a4-parcels", "fill-color", state.reading === "vegetation"
        ? ["step", ["get", "veg_pct"], "#eee6cc", 20, "#cbd8b7", 50, "#98b487", 80, "#4c7257"]
        : ["get", "history_color"]);
      map.setPaintProperty("a4-parcels", "fill-opacity", state.reading === "vegetation" ? 0.91 : 0.65);
      if (state.scale === "study") element("caption-detail").textContent = `${features.filter(matches).length} of 14 sampled lots - ${state.reading === "vegetation" ? "2022 spectral vegetation response" : "1996 and 2018 image readings"}`;
    };

    const setScale = (scale: "city" | "study") => {
      state.scale = scale;
      root.classList.toggle("is-study", scale === "study");
      state.borough = "all";
      closeParcel();
      element("city-reading").hidden = scale !== "city";
      element("study-reading").hidden = scale !== "study";
      element("city-key").hidden = scale !== "city";
      element("study-key").hidden = scale !== "study";
      element("caption-place").textContent = scale === "city" ? "New York City" : "East New York";
      element("caption-detail").textContent = scale === "city" ? "24,213 mapped vacant lots - 26v2" : "14 sampled lots - 2022 spectral vegetation response";
      document.querySelectorAll<HTMLButtonElement>("[data-scale]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.scale === scale)));
      document.querySelectorAll<HTMLButtonElement>("[data-borough]").forEach((button) => button.setAttribute("aria-pressed", "false"));
      if (state.ready) {
        cityLayers.forEach((id) => map.setLayoutProperty(id, "visibility", scale === "city" ? "visible" : "none"));
        studyLayers.forEach((id) => map.setLayoutProperty(id, "visibility", scale === "study" ? "visible" : "none"));
        map.setFilter("a4-city-fill", null);
        map.setFilter("a4-city-edge", null);
        fit(scale === "city" ? manifest.bounds.citywide : manifest.bounds.screening);
      }
      updateReading();
    };

    const boroughList = element("borough-list");
    const boroughCaption = document.createElement("p");
    boroughCaption.className = "borough-list-caption";
    boroughCaption.textContent = "recorded lots - mapped lots";
    boroughList.append(boroughCaption);
    for (const borough of manifest.boroughs) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "borough-row";
      row.dataset.borough = borough.code;
      row.setAttribute("aria-pressed", "false");
      row.setAttribute("aria-label", `Explore ${borough.name}: ${borough.records} vacant records, ${borough.mapped} mapped lots`);
      const label = document.createElement("span");
      label.textContent = borough.name;
      const numbers = document.createElement("small");
      numbers.textContent = `${borough.records} - ${borough.mapped}`;
      row.append(label, numbers);
      row.addEventListener("click", () => {
        if (!state.ready) return;
        state.borough = borough.code;
        map.setFilter("a4-city-fill", ["==", ["get", "borough"], borough.code]);
        map.setFilter("a4-city-edge", ["==", ["get", "borough"], borough.code]);
        document.querySelectorAll<HTMLButtonElement>("[data-borough]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.borough === borough.code)));
        element("caption-place").textContent = borough.name;
        element("caption-detail").textContent = `${borough.mapped} mapped of ${borough.records} vacant records`;
        if (borough.bounds) fit(borough.bounds);
      });
      boroughList.append(row);
    }

    const cityBounds = manifest.bounds.screening;
    const windowFeature: FeatureCollection<Polygon> = { type: "FeatureCollection", features: [{ type: "Feature", properties: { name: "Pilot study window" }, geometry: { type: "Polygon", coordinates: [[[cityBounds[0], cityBounds[1]], [cityBounds[2], cityBounds[1]], [cityBounds[2], cityBounds[3]], [cityBounds[0], cityBounds[3]], [cityBounds[0], cityBounds[1]]]] } }] };

    map.on("load", () => {
      map.addSource("a4-city", { type: "geojson", data: asset("data/assignment04/citywide.geojson"), tolerance: 0.6 });
      map.addSource("a4-screen", { type: "geojson", data: screening });
      map.addSource("a4-parcel-source", { type: "geojson", data: parcels });
      map.addSource("a4-window", { type: "geojson", data: windowFeature });
      map.addLayer({ id: "a4-city-fill", type: "fill", source: "a4-city", paint: { "fill-color": "#78906a", "fill-opacity": 0.76 } });
      map.addLayer({ id: "a4-city-edge", type: "line", source: "a4-city", minzoom: 12.5, paint: { "line-color": "#59764f", "line-opacity": 0.42, "line-width": 0.6 } });
      map.addLayer({ id: "a4-window-line", type: "line", source: "a4-window", paint: { "line-color": "#b28d6b", "line-opacity": 0.8, "line-width": 1.1, "line-dasharray": [3, 3] } });
      map.addLayer({ id: "a4-screening", type: "fill", source: "a4-screen", layout: { visibility: "none" }, paint: { "fill-color": "#c8d3bb", "fill-opacity": 0.59 } });
      map.addLayer({ id: "a4-screening-edge", type: "line", source: "a4-screen", layout: { visibility: "none" }, paint: { "line-color": "#9fb08f", "line-opacity": 0.65, "line-width": 0.6 } });
      map.addLayer({ id: "a4-selected-halo", type: "line", source: "a4-parcel-source", filter: ["==", ["get", "bbl"], ""], paint: { "line-color": "#fbf9ee", "line-width": 7 }, layout: { visibility: "none" } });
      map.addLayer({ id: "a4-parcels", type: "fill", source: "a4-parcel-source", paint: { "fill-color": ["step", ["get", "veg_pct"], "#eee6cc", 20, "#cbd8b7", 50, "#98b487", 80, "#4c7257"], "fill-opacity": 0.91 }, layout: { visibility: "none" } });
      map.addLayer({ id: "a4-parcel-edge", type: "line", source: "a4-parcel-source", paint: { "line-color": ["get", "history_color"], "line-width": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 2.5] }, layout: { visibility: "none" } });
      map.addLayer({ id: "a4-selected-edge", type: "line", source: "a4-parcel-source", filter: ["==", ["get", "bbl"], ""], paint: { "line-color": "#344d38", "line-width": 3 }, layout: { visibility: "none" } });
      state.ready = true;
      renderList();
      setScale("city");
      map.once("idle", () => { element("map-loading").hidden = true; });
    });

    map.on("click", (event) => {
      if (state.scale !== "study" || !state.ready) return;
      const { x, y } = event.point;
      const clicked = map.queryRenderedFeatures([[x - 7, y - 7], [x + 7, y + 7]], { layers: ["a4-parcels", "a4-parcel-edge"] });
      if (clicked[0]?.properties?.bbl) selectParcel(String(clicked[0].properties.bbl));
    });
    map.on("mousemove", (event) => {
      if (!state.ready || state.scale !== "study") return;
      const { x, y } = event.point;
      const hovered = map.queryRenderedFeatures([[x - 4, y - 4], [x + 4, y + 4]], { layers: ["a4-parcels"] });
      map.getCanvas().style.cursor = hovered.length ? "pointer" : "";
    });
    map.on("error", (event) => {
      console.warn("Map resource could not load", event.error);
      if ("sourceId" in event && typeof event.sourceId === "string" && event.sourceId.startsWith("a4-")) showError("One of the project layers could not load. Refresh this page to try again; the source files are also included in the project download.");
    });

    document.querySelectorAll<HTMLButtonElement>("[data-scale]").forEach((button) => button.addEventListener("click", () => setScale(button.dataset.scale as "city" | "study")));
    element("enter-study").addEventListener("click", () => setScale("study"));
    element<HTMLSelectElement>("history-filter").addEventListener("change", (event) => { state.history = (event.target as HTMLSelectElement).value; renderList(true); });
    element<HTMLSelectElement>("vegetation-filter").addEventListener("change", (event) => { state.vegetation = (event.target as HTMLSelectElement).value; renderList(true); });
    element("clear-filters").addEventListener("click", () => {
      state.history = "all";
      state.vegetation = "all";
      element<HTMLSelectElement>("history-filter").value = "all";
      element<HTMLSelectElement>("vegetation-filter").value = "all";
      renderList(true);
    });
    document.querySelectorAll<HTMLInputElement>('input[name="reading"]').forEach((radio) => radio.addEventListener("change", () => { state.reading = radio.value as "vegetation" | "history"; updateReading(); }));
    document.querySelectorAll<HTMLButtonElement>("[data-evidence]").forEach((button) => button.addEventListener("click", () => { state.evidence = button.dataset.evidence as "archive" | "2022"; updateImages(); }));
    element<HTMLInputElement>("image-comparison").addEventListener("input", imageComparison);
    element("close-parcel").addEventListener("click", closeParcel);
    element("map-zoom-in").addEventListener("click", () => map.zoomIn({ duration: duration(250) }));
    element("map-zoom-out").addEventListener("click", () => map.zoomOut({ duration: duration(250) }));
    element("map-home").addEventListener("click", () => setScale(state.scale));
    element("map-north").addEventListener("click", () => map.resetNorth({ duration: duration(250) }));
    const key = element("atlas-map-key");
    key.hidden = compact();
    element("toggle-legend").setAttribute("aria-expanded", String(!key.hidden));
    element("toggle-legend").addEventListener("click", () => { key.hidden = !key.hidden; element("toggle-legend").setAttribute("aria-expanded", String(!key.hidden)); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeParcel(); });
    renderList();
  };

  start().catch((error: unknown) => {
    console.error(error);
    showError("The field index could not start. Check the connection and reload; the project repository contains the same data and map files.");
  });
}
