export function nameInitials(name) {
  const parts = name.split(" ");
  if (parts.length === 1) {
    return `${parts[0][0]}`;
  } else if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`;
  }
  return "";
}

export function properCase(str) {
  return str
    .toLowerCase()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function parseSourceUrl(url) {
  try {
    // Decode the URL in case it contains URL-encoded characters
    const decodedUrl = decodeURIComponent(url);

    const match = decodedUrl.match(/(\w+)\.(\w+)\.org\/wiki\//);
    if (!match) {
      throw new Error("URL pattern does not match");
    }

    const srcLang = match[1]; 
    const srcProject = match[2];
    const srcFileName = decodedUrl.split("/").pop();

    return { srcLang, srcProject, srcFileName };
  } catch (error) {
    return false;
  }
};
