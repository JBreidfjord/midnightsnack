module.exports = {convert};

const showdown = require('showdown');
const fs = require('fs');

let converter = new showdown.Converter({requireSpaceBeforeHeadingText: true, encodeEmails: false});

function convert(tmpDir) {
  fs.readFile(`${tmpDir}/article.md`, (error, data) => {
    if (error) {
      console.error(error);
      return error;
    }
    let text = data.toString();
    let html = converter.makeHtml(text);
    fs.writeFile(`${tmpDir}/article.html`, html, (error) => {
      if (error) {
        console.error(error);
        return error;
      }
      return true;
    });
  });
};