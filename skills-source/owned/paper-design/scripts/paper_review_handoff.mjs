async function getFs() {
  return await import('node:fs/promises');
}

async function getPath() {
  return (await import('node:path')).default;
}

function extForMime(mimeType) {
  switch (mimeType) {
    case 'image/png':
      return 'png';
    case 'image/webp':
      return 'webp';
    case 'image/jpeg':
    default:
      return 'jpg';
  }
}

function sanitizeName(value) {
  return String(value || 'paper-shot')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'paper-shot';
}

function extractImageContent(toolOutput) {
  const content = toolOutput?.output?.content;
  if (!Array.isArray(content)) {
    throw new Error('Paper screenshot tool output did not include a content array.');
  }

  const image = content.find((item) => item?.type === 'image' && item?.data);
  if (!image) {
    throw new Error('Paper screenshot tool output did not include an image payload.');
  }

  return {
    base64: image.data,
    mimeType: image.mimeType || 'image/jpeg',
  };
}

export async function savePaperScreenshotForReview(nodeId, options = {}) {
  if (!nodeId) throw new Error('nodeId is required');

  const fs = await getFs();
  const path = await getPath();

  const {
    scale = 1,
    name,
    outDir = path.join(codex.tmpDir, 'paper-review'),
  } = options;

  const toolOutput = await codex.tool('mcp__paper__get_screenshot', { nodeId, scale });
  const { base64, mimeType } = extractImageContent(toolOutput);
  const ext = extForMime(mimeType);
  const basename = sanitizeName(name || nodeId);

  await fs.mkdir(outDir, { recursive: true });

  const filePath = path.join(outDir, `${basename}.${ext}`);
  await fs.writeFile(filePath, Buffer.from(base64, 'base64'));

  return {
    path: filePath,
    mimeType,
    item: {
      type: 'local_image',
      path: filePath,
    },
  };
}

export async function buildVisualReviewerItems(nodeId, reviewPrompt, options = {}) {
  const screenshot = await savePaperScreenshotForReview(nodeId, options);
  return {
    screenshot,
    items: [
      ...(reviewPrompt ? [{ type: 'text', text: reviewPrompt }] : []),
      screenshot.item,
    ],
  };
}
