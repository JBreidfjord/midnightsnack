const showdown = require('showdown');
const fs = require('fs');

const converter = new showdown.Converter({requireSpaceBeforeHeadingText: true, encodeEmails: false});

module.exports.convert = function (tmpDir) {
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

module.exports.titleConvert = function (title) {
  let html = converter.makeHtml(title);
  console.log(html)
};