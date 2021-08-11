$(document).ready(function(){
  const tmpId = $("#tmpId").val();
  const articleId = $("#articleId").val();
  console.log(articleId);
  console.log(tmpId);

  function startEdit() {
      axios.get(`/edit/${tmpId}`)
      .then(function (response) {
          articleMd = response.data;
          document.getElementById("editable-article-content").innerHTML = (
              `<div><pre><code class="nohighlight" id="editor-block" contenteditable>${articleMd}</code></pre></div>`
          );
      })
      .catch(function (error) {
          console.log(error);
      });
  };
    
  function submitEdit() {
      articleMd = document.getElementById("editor-block").innerHTML;
      form = new FormData();
      form.append("article_md", articleMd);
      axios.post(`/edit/${tmpId}`, form, {
          headers: {
              "Accept": "multipart/form-data",
              "Content-Type": "multipart/form-data"
          }
      })
      .then(function (response) {
          articleDiv = document.getElementById("editable-article-content")
          articleDiv.innerHTML = response.data;
          hljs.highlightAll();
      })
      .catch(function (error) {
          console.log(error);
      });
  };

  function commitPost() {
      result = confirm("Are you sure?\nThis will commit the article.")
      if (result == true) {
          axios.post(`/posts/edit/${articleId}`, {tmp_id: tmpId})
          .then(function (response) {
              console.log(response);
              if (response.status == 200) {
                  window.location = response.data.url
              }
          })
          .catch(function (error) {
              console.log(error);
              alert(error);
          });
      };
  };
  $("#start-edit").click(startEdit);
  $("#submit-edit").click(submitEdit);
  $("#commit-article").click(commitPost);
  $(document).on("keydown", "#editor-block", function(e){
      if(e.keyCode == 9){
          e.preventDefault();
          document.execCommand("insertHTML", false, "\u00a0\u00a0\u00a0\u00a0");
      }
  });
});