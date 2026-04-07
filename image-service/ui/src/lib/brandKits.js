export const emptyBrandKitDraft = {
  name: '',
  background: '',
  lighting: '',
  tone: '',
  framing: '',
};

export const buildBrandStyle = ({ background, lighting, tone, framing }) =>
  [
    background ? `background: ${background}` : null,
    lighting ? `lighting: ${lighting}` : null,
    tone ? `tone: ${tone}` : null,
    framing ? `framing: ${framing}` : null,
  ]
    .filter(Boolean)
    .join(', ');

export const buildBrandKitSnapshot = ({ name = '', background = '', lighting = '', tone = '', framing = '' }) => ({
  ...(name ? { name } : {}),
  background,
  lighting,
  tone,
  framing,
});
