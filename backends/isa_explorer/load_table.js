// Chunked data loading for better performance
function loadDataInChunks(data, chunkSize = 500, delay = 50) {
    if (!Array.isArray(data) || data.length === 0) return;

    const totalChunks = Math.ceil(data.length / chunkSize);
    let currentChunk = 0;

    function loadNextChunk() {
        const startIndex = currentChunk * chunkSize;
        const endIndex = Math.min(startIndex + chunkSize, data.length);
        const chunk = data.slice(startIndex, endIndex);

        try {
            if (currentChunk === 0) {
                table.clearData();
                table.setData(chunk);
            } else {
                table.addData(chunk);
            }

            currentChunk++;
            console.log(`Chunk ${currentChunk}/${totalChunks}: ${endIndex}/${data.length} items`);

            if (currentChunk < totalChunks) {
                setTimeout(loadNextChunk, delay);
            } else {
                console.log('All data loaded successfully.');
            }
        } catch (error) {
            console.error('Error loading chunk:', error);
            if (currentChunk < totalChunks) setTimeout(loadNextChunk, delay);
        }
    }

    loadNextChunk();
}
