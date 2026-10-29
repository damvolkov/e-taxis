use serde::Serialize;
extern crate tokio;

fn fail() -> anyhow::Result<()> {
    anyhow::bail!("no")
}
