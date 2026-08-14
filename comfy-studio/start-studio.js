module.exports = {
  daemon: true,
  run: [
    {
      when: "{{!running('start.js')}}",
      method: "script.start",
      params: {
        uri: "start.js"
      }
    },
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "studio",
        message: [
          "uv pip install -r requirements.txt",
          "python server.py --host 127.0.0.1 --port {{port}}"
        ],
        on: [{
          event: "/(http:\\/\\/[0-9.:]+)/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "{{input.event[1]}}"
      }
    }
  ]
}
