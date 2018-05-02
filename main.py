from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, session, logging, send_file, Markup
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
import optimizer as opt
from functools import wraps
import datetime
from azure.storage.file import FileService
import os
import os.path


app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))


# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Mark1204'
app.config['MYSQL_DB'] = 'efficientfrontier'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Initialize MySQL
mysql = MySQL(app)

@app.route('/')
def index():
  return render_template('home.html')





# Check if user logged in

def is_logged_in(f):
  @wraps(f)
  def wrap(*args, **kwargs):
    if 'logged_in' in session:
      return f(*args, **kwargs)
    else:
      flash('Unauthorized, Please login', 'danger')
      return redirect(url_for('login'))  

  return wrap


# Register form class
class RegisterForm(Form):
  name = StringField('Name', [validators.Length(min = 1, max = 50)])
  company = StringField ('Company', [validators.Length(max = 50)])
  email = StringField('Email', [validators.Length(min = 6, max = 50)])
  password = PasswordField('Password', [
    validators.DataRequired(),
    validators.EqualTo('confirm', message = 'Password do not match')
  ])
  confirm = PasswordField('Confirm Password')


# Download Template File

@app.route('/tempfile_download')
@is_logged_in
def tempfile_download():
  return send_file('ef_template.xlsx', attachment_filename = 'ef_template.xlsx')





# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
  form = RegisterForm(request.form)
  if request.method == 'POST' and form.validate():
    name = form.name.data
    company = form.company.data
    email = form.email.data
    password = sha256_crypt.encrypt(str(form.password.data))

    # Create Cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute('INSERT INTO users(name, company, email, password) VALUES(%s, %s, %s, %s)', (name, company, email, password))

    # Commit to DB
    mysql.connection.commit()

    # Close connection
    cur.close()
    session['logged_in'] = True
    session['email'] = email

    flash('You are now registered and logged in!', 'success')

    return redirect(url_for('files'))

  return render_template('register.html', form=form)  





# Login Page
@app.route('/login', methods = ['GET', 'POST'])
def login():
  if request.method == 'POST':
    # Get Form Fields
    email = request.form['email']
    password_candidate = request.form['password']


    # Create Cursor
    cur = mysql.connection.cursor()

    # Get user by name
    result = cur.execute ('SELECT * FROM users WHERE email = %s', [email])

    if result > 0:
      # Get stored hash
      data = cur.fetchone()
      password = data['password']

      # Compare Passwords
      if sha256_crypt.verify(password_candidate, password):
        # Passed
        session['logged_in'] = True
        session['email'] = email

        flash ('You are now logged in', 'success')
        return redirect(url_for ('files'))
      else:
        error = 'Invalid Login'
        return render_template('login.html', error = error)

      # Close connection
      cur.close()
    else:
      error = 'User not found'
      return render_template('login.html', error = error)

  return render_template('login.html')  





# Logout
@app.route('/logout')
@is_logged_in
def logout():
  session.clear()
  flash('You are now logged out', 'success')
  return redirect(url_for('login'))


  


# File dashboard
@app.route('/files', methods = ["GET"])
@is_logged_in
def files():
  # Create Cursor
  cur = mysql.connection.cursor()

  #Get files
  result = cur.execute('SELECT filename, USER, createdon FROM files_uploaded WHERE USER = %s', [session['email']])

  files = cur.fetchall()

  #Get user's name
  cur.execute ('SELECT name FROM users WHERE email = %s', [session['email']])
  name = cur.fetchone()
  name = name['name']

  if result > 0:
    return render_template('files.html', files = files, name = name)

  else:
    msg = 'No files found, please upload your files first.'
    return render_template('files.html', error = msg, name = name)

  # Close connection
  cur.close()


@app.route('/files', methods = ["POST"])
@is_logged_in
def upload():
  AzureStorageAccount = 'effiles'
  key = 'axLykwdLsUwKTDY5flU6ivGrt9obV38k2UMVDCSpLYE3K6jAkwsjWOThQydhuMSWHfx6lTq102gdkas/GyKhEA=='
  up_path = 'uploads'
  path1 = 'efficientfrontier'
  file_service = FileService(account_name = AzureStorageAccount, account_key = key)

  target = os.path.join(APP_ROOT, 'uploads/')

  if request.method == 'POST':
    if not os.path.isdir(target):
      os.mkdir(target)
    

 
    for file in request.files.getlist("file"):
      filename = file.filename
      destination = '/'.join([target, filename])
      #print (destination)
      file.save(destination)       # Save the file to local server
      now = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
      filename_new = os.path.splitext(filename)[0] + '_' + now + os.path.splitext(filename)[1]
      file_service.create_file_from_path (path1, up_path, filename_new, destination)    # Upload the file to Azure Storage Account
      # Create Cursor
      cur = mysql.connection.cursor()

      # Execute
      cur.execute ('INSERT INTO files_uploaded (filename, USER, AzureAccount, AzureShare, Directory) VALUES(%s, %s, %s, %s, %s)', (filename_new, session['email'], AzureStorageAccount, path1, up_path))  

      # Commit to DB
      mysql.connection.commit()

      # Close connection
      cur.close()

      flash ('File Uploaded', 'success')
      os.remove(destination)  # Remove locally saved file
    
  return redirect(url_for('files'))




@app.route('/optimizer/<string:filename>', methods = ['GET', 'POST'])
@is_logged_in
def optimize(filename):
  data, AzureStorageAccount, path1, down_path, outfilename, key = opt.get_result(filename)
  '''response = {'AzureStorageAccount': AzureStorageAccount,
              'Folder1': path1,
              'Folder2': down_path,
              'Output File': outfilename,
              'data': data,
              'StorageAccountKey': key} 
  res = jsonify(response)'''

  # Create Cursor
  cur = mysql.connection.cursor()

  # Execute
  result = cur.execute('SELECT filename FROM result_files WHERE filename = %s', [outfilename])
  
  if result == 0:
    
    cur.execute ('INSERT INTO result_files (filename, USER, AzureAccount, AzureShare, Directory) VALUES(%s, %s, %s, %s, %s)', (outfilename, session['email'], AzureStorageAccount, path1, down_path))


  # Commit to DB
  mysql.connection.commit()

  # Close connection
  cur.close()
  
  flash ('File optimization completed! Please click <a href = \"/results\" class = \"alert-link\" >here</a> to view.', 'success')
  return redirect(url_for('files'))



@app.route('/delete_upload/<string:filename>', methods = ['GET', 'POST'])
@is_logged_in
def delete_upload(filename):
  AzureStorageAccount = 'effiles'
  key = 'axLykwdLsUwKTDY5flU6ivGrt9obV38k2UMVDCSpLYE3K6jAkwsjWOThQydhuMSWHfx6lTq102gdkas/GyKhEA=='
  up_path = 'uploads'
  path1 = 'efficientfrontier'
  file_service = FileService(account_name = AzureStorageAccount, account_key = key)
  file_service.delete_file (path1, up_path, filename)
  # Create Cursor
  cur = mysql.connection.cursor()

  # Execute
  cur.execute ('DELETE FROM files_uploaded WHERE filename = %s', [filename])

  # Commit to DB
  mysql.connection.commit()

  # Close connection
  cur.close()

  flash ('File Deleted', 'success')
    
  return redirect(url_for('files'))




@app.route('/results', methods = ['GET', 'POST'])
@is_logged_in
def results():
  # Create Cursor
  cur = mysql.connection.cursor()

  #Get files
  result = cur.execute('SELECT filename, USER, createdon FROM result_files WHERE USER = %s', [session['email']])

  files = cur.fetchall()

  #Get user's name
  cur.execute ('SELECT name FROM users WHERE email = %s', [session['email']])
  name = cur.fetchone()
  name = name['name']

  if result > 0:
    return render_template('results.html', files = files, name = name)

  else:
    msg = Markup('No result files found, please optimize your <a href = \"files\" class =\"alert-link\">uploaded files</a> first.')
    return render_template('results.html', error = msg, name = name)

  # Close connection
  cur.close()





@app.route('/download_result/<string:filename>', methods = ['GET', 'POST'])
@is_logged_in
def download_result(filename):
  AzureStorageAccount = 'effiles'
  key = 'axLykwdLsUwKTDY5flU6ivGrt9obV38k2UMVDCSpLYE3K6jAkwsjWOThQydhuMSWHfx6lTq102gdkas/GyKhEA=='
  down_path = 'results'
  path1 = 'efficientfrontier'
  file_service = FileService(account_name = AzureStorageAccount, account_key = key)
  target = os.path.join(APP_ROOT, 'results/')
  destination = '/'.join([target, filename])
  file_service.get_file_to_path (path1, down_path, filename, destination)

  
  return send_file(destination, attachment_filename = filename)
  




@app.route('/delete_result/<string:filename>', methods = ['GET', 'POST'])
@is_logged_in
def delete_result(filename):
  AzureStorageAccount = 'effiles'
  key = 'axLykwdLsUwKTDY5flU6ivGrt9obV38k2UMVDCSpLYE3K6jAkwsjWOThQydhuMSWHfx6lTq102gdkas/GyKhEA=='
  down_path = 'results'
  path1 = 'efficientfrontier'
  file_service = FileService(account_name = AzureStorageAccount, account_key = key)
  file_service.delete_file (path1, down_path, filename)
  # Create Cursor
  cur = mysql.connection.cursor()

  # Execute
  cur.execute ('DELETE FROM result_files WHERE filename = %s', [filename])

  # Commit to DB
  mysql.connection.commit()

  # Close connection
  cur.close()

  target = os.path.join(APP_ROOT, 'results/')
  destination = '/'.join([target, filename])
  
  if os.path.exists(destination):
    os.remove(destination)


  flash ('File Deleted', 'success')
    
  return redirect(url_for('results'))




#if __name__ == '__main__':
app.secret_key = 'secret123'
  #app.run(debug = True)
