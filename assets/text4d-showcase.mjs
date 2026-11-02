// User choices refer to the former gallery's Scene 22–66 labels.
// Scene 22 was indoor sample_000 (the kitchen-and-dining prompt).
export const TEXT4D_WEBSITE_NUMBERS = Object.freeze([
  22,24,30,31,33,36,37,38,39,40,43,46,47,48,49,50,52,53,56,57,58,60,65,66,
]);
export const TEXT4D_INDOOR_PREFIX = "text4d-indoor-";
export const TEXT4D_SHOWCASE_IDS = Object.freeze(TEXT4D_WEBSITE_NUMBERS.map(number =>
  TEXT4D_INDOOR_PREFIX + String(number-22).padStart(3,"0")));
export function applyText4DShowcase(manifest) {
  const gallery = manifest.generation;
  const byId = new Map(gallery.cases.map(example => [example.id,example]));
  const approved = TEXT4D_SHOWCASE_IDS.map(id => {
    if (!byId.has(id)) throw new Error("Approved Text-to-4D example missing: " + id);
    return byId.get(id);
  });
  return {...manifest,generation:{...gallery,cases:approved}};
}
