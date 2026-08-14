module.exports = {
  run: [{
    method: "fs.download",
    params: {
      uri: "https://huggingface.co/ai-forever/Real-ESRGAN/resolve/main/RealESRGAN_x2.pth?download=true",
      dir: "app/models/upscale_models"
    }
  }]
}
