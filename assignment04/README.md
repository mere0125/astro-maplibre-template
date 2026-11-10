# The Temporary Forest

Assignment 4 - Representation and Interactivity

Mere Cui - 10 November 2026

This interactive field index carries the existing project from a citywide administrative inventory into a close reading of fourteen East New York lots. It accompanies the proposed narrative atlas. It does not replace the final atlas proposed as a static PDF.

The question is how to represent the living surfaces hidden within the category “vacant land” while keeping the limits of the evidence visible. The citywide map provides context. The East New York pilot provides historical snapshots and a measured vegetation response.

## Submission

The [Assignment 4 brief](https://designpractices.org/assignments/04-representation/) asks for the files needed to run the interactive map and or a GitHub-hosted project link, together with a text file documenting where the code comes from. The work will be presented in small groups on November 13.

- [Interactive field index](https://mere0125.github.io/astro-maplibre-template/assignment_04/)
- [Project repository](https://github.com/mere0125/astro-maplibre-template)
- `CODE_PROVENANCE.txt` - mandatory code-origin statement

A PDF is not listed as an Assignment 4 deliverable. This submission is distinct from the tutorial submissions, although they share a repository and some source data.

## The three scales

| Scale | Evidence | Interpretation |
| --- | --- | --- |
| New York City | 24,663 PLUTO 26v2 records coded Vacant Land; 24,213 have usable nonempty geometry | An administrative geography of vacancy across the five boroughs |
| East New York | The original 254 matched vacant lots from the earlier project work | A defined screening window, not an official neighbourhood boundary |
| Fourteen lots | Two archival condition readings and 2022 vegetation measurements for each parcel | A purposive pilot that supports descriptive comparisons |

The fourteen lots were drawn from the thirty-six largest matched parcels interpreted in the earlier work. They belong to two groups with usable earlier observations: eight appear open in both 1996 and 2018, and six show a building in 1996 and open ground in 2018. Current vacancy comes from the 2026 administrative record.

## Reading the map

Begin with the citywide context, then enter East New York. Select a parcel through the map or its list entry. Compare the dated aerial excerpts and the 2022 vegetation response, and use the filters to inspect the historical groups and vegetation classes.

Each image must retain its year, source, spatial extent, and parcel outline. The image comparison supports inspection of visible differences; it does not identify an exact demolition date or prove that a lot remained continuously vacant between observations.

The interface uses restrained sage and paper colours, Times typography, quiet botanical details, actual parcel shapes, and deliberate changes in scale. The visual hierarchy is intended to support close reading rather than turn every dataset into an equally prominent layer.

## Measurements

NDVI is calculated as the near-infrared value minus the red value, divided by their sum. The parcel percentage is the share of valid assigned pixels whose NDVI is greater than 0.20. Red and near infrared are bands 1 and 4 of the retained four-band 2022 NAIP image.

The four displayed classes are under 20 percent, 20 to under 50 percent, 50 to under 80 percent, and 80 percent or more. These are display classes for the measured percentage, not biological definitions of forest.

The earlier analysis found group medians of 63.1 percent for the eight lots open in both archival years and 63.6 percent for the six lots with a building in 1996 and open ground in 2018. This pilot does not support a simple claim that older vacancy is greener. Individual values range from 0.3 to 92.3 percent.

## Data and limits

The retained sources are NYC Department of City Planning PLUTO and MapPLUTO 26v2, NYC Office of Technology and Innovation aerial imagery from 1996 and 2018, and USDA NAIP imagery from 2022. The project retains the earlier GeoPackages, raster inputs, processing scripts, and audit tables.

The 2026 administrative count contains 423 null geometries and 27 empty geometries. These records remain part of the citywide inventory but cannot be drawn as polygons. Historical readings use current tax-lot boundaries, which may differ from historical parcel boundaries.

NDVI measures spectral vegetation response. It does not establish tree canopy, species composition, habitat quality, public access, ecological benefit, or present-day surface condition. The small purposive sample cannot represent all vacant land in New York City. Field observations proposed for the final atlas have not been presented as completed observations in this assignment.

## Technical handoff

The source lives in the existing `astro-maplibre-template` repository. The Assignment 4 route is `assignment_04`. The repository includes its dependency lockfile and GitHub Pages build workflow.

With a Node version supported by the repository's `package.json`, install dependencies using `npm install`, then run `npm run dev`. The build command is `npm run build`. Network access is needed for the basemap tiles and external font or glyph resources used by the basemap.

GIS preparation is scripted and traceable to the retained source layers. Astro creates the web page and MapLibre renders the interactive map. This is not a direct QGIS web export. See `CODE_PROVENANCE.txt` for the actual template, tutorial, library, data, and OpenAI Codex contributions.

## 演讲时怎么理解

这次作业是期末项目的交互式索引。先用全纽约的空置地块说明背景，再进入 East New York 的筛选范围，最后点开一个具体地块，看它在不同年份的证据。

1996 和 2018 是航拍影像的观察年份。2022 是 NDVI 的影像年份。2026 是 MapPLUTO 的行政分类年份，不能说成 2026 的航拍观察。图中每个绿色百分比表示该地块中 NDVI 大于 0.20 的有效像素比例，不等于树冠覆盖率，也不等于森林面积。

最值得讲的结果是：长期开放组与后来清空组的植被响应中位数非常接近，因此“空置越久就越绿”并不是这组样本能支持的结论。交互的作用是让观众自行查看这些差异及其证据。
