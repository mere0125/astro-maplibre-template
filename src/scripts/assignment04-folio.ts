import type { Feature, MultiPolygon, Polygon } from "geojson";

type SurfaceParcel = Feature<Polygon | MultiPolygon, {
  bbl: string;
  address: string;
  lotarea: number;
  veg_pct: number;
  history_group: "open_in_both" | "built_then_open";
  history_label: string;
  history_color: string;
}>;
type SpecimenManifest = {
  common_extent_feet: number;
  specimens: Record<string, { file: string }>;
};
type FolioOptions = {
  features: SurfaceParcel[];
  images: Record<string, Record<string, string>>;
  specimens: SpecimenManifest;
  asset: (path: string) => string;
  locate: (bbl: string) => void;
};

const titleCase = (text: string) => text.toLowerCase().replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
const node = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string) => {
  const result = document.createElement(tag);
  result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
};

export const createSurfaceFolio = ({ features, images, specimens, asset, locate }: FolioOptions) => {
  const pair = document.getElementById("surface-pair")!;
  const collection = document.getElementById("specimen-collection")!;
  const featured = ["3037250012", "3040630052"];
  for (const bbl of featured) {
    const feature = features.find((item) => item.properties.bbl === bbl);
    if (!feature) continue;
    const p = feature.properties;
    const figure = node("figure", "paired-lot");
    const button = node("button", "paired-image");
    button.type = "button";
    button.setAttribute("aria-label", `Locate ${titleCase(p.address)} on the map`);
    const image = node("img", "");
    image.src = asset(images[bbl]["2022_rgb"]);
    image.alt = `2022 NAIP image of ${titleCase(p.address)} with the current parcel outlined`;
    image.loading = "lazy";
    image.width = image.height = 512;
    button.append(image, node("span", "pair-map-link leaf-action", "locate this parcel"));
    button.addEventListener("click", () => locate(bbl));
    const caption = node("figcaption", "paired-caption");
    caption.append(node("h4", "", titleCase(p.address)));
    const response = node("p", "paired-response");
    response.append(node("strong", "", `${p.veg_pct.toFixed(1)}%`), node("span", "", "2022 vegetation response"));
    caption.append(response, node("p", "paired-area", `${Math.round(p.lotarea)} square feet recorded in the lot data`));
    figure.append(button, caption);
    pair.append(figure);
  }

  document.getElementById("specimen-scale-note")!.textContent = `Each image occupies a ${specimens.common_extent_feet}-foot square. Grid north is at the top - EPSG 2263.`;
  collection.style.setProperty("--scale-fraction", String(50 / specimens.common_extent_feet));
  const median = (values: number[]) => {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };
  const groups = ["open_in_both", "built_then_open"] as const;
  const summaries = groups.map((group) => {
    const members = features.filter((feature) => feature.properties.history_group === group);
    return { group, count: members.length, median: median(members.map((feature) => feature.properties.veg_pct)) };
  });
  document.getElementById("surface-group-summary")!.textContent = `Across the full sample, the ${summaries[0].count} lots open at both archival dates have a median response of ${summaries[0].median.toFixed(1)} percent. The ${summaries[1].count} lots built in 1996 and open in 2018 have a median of ${summaries[1].median.toFixed(1)} percent. These medians are similar. This small, selected sample does not establish that earlier vacancy produces more vegetation.`;

  const specimen = (feature: SurfaceParcel) => {
    const p = feature.properties;
    const button = node("button", "surface-specimen");
    button.type = "button";
    button.style.setProperty("--specimen-history", p.history_color);
    button.setAttribute("aria-label", `Locate ${titleCase(p.address)}, BBL ${p.bbl}, ${p.veg_pct.toFixed(1)} percent vegetation response, ${p.history_label}`);
    const imageWrap = node("span", "specimen-image");
    const image = node("img", "");
    image.src = asset(specimens.specimens[p.bbl].file);
    image.alt = "";
    image.loading = "lazy";
    image.width = image.height = 700;
    imageWrap.append(image, node("span", "specimen-image-scale", "50 ft"));
    const caption = node("span", "specimen-caption");
    caption.append(node("span", "specimen-address", titleCase(p.address)), node("span", "specimen-percent", `${p.veg_pct.toFixed(1)}%`));
    const history = node("span", "specimen-history", p.history_label);
    button.append(imageWrap, caption, history, node("span", "specimen-bbl", `BBL ${p.bbl}`));
    button.addEventListener("click", () => locate(p.bbl));
    return button;
  };
  const render = (order: "response" | "history") => {
    collection.replaceChildren();
    const sorted = [...features].sort((a, b) => b.properties.veg_pct - a.properties.veg_pct);
    if (order === "response") {
      const grid = node("div", "specimen-grid");
      sorted.forEach((feature) => grid.append(specimen(feature)));
      collection.append(grid);
    } else {
      for (const summary of summaries) {
        const section = node("section", "specimen-history-group");
        section.append(node("h4", "", summary.group === "open_in_both" ? "Open in both archival images" : "Built in 1996, open in 2018"));
        section.append(node("p", "group-measure", `${summary.count} parcels - median ${summary.median.toFixed(1)} percent`));
        const grid = node("div", "specimen-grid");
        sorted.filter((feature) => feature.properties.history_group === summary.group).forEach((feature) => grid.append(specimen(feature)));
        section.append(grid);
        collection.append(section);
      }
    }
  };
  document.querySelectorAll<HTMLInputElement>('input[name="surface-order"]').forEach((radio) => radio.addEventListener("change", () => render(radio.value as "response" | "history")));
  render("response");
};
