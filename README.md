TODO
- [ ] Wider angle lens, or rotate servo and process to create pano image
- [ ] Add path tracking (for now, full naive) and adjust movement to steer away from prev explored areas
- [ ] Annotate image before processing with vllm, like yolo or add angle markers
- [ ] Add log compression - anything older than the nth most recent log, combine it, compressing more and more (using a language model to summarize) the older it gets. Right now it just clips the log to the nth most recent