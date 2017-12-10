-- ## Create Database

create database resas2017;
use resas2017;

-- ## Create Tables
-- ### keywords
create table if not exists keywords (
  id int not null primary key auto_increment,
  keyword varchar(255) not null unique,
  index idx_keyword(keyword)
);

-- ### stores
create table if not exists stores (
  id int not null primary key auto_increment,
  name varchar(255) not null unique,
  thumbnail text,
  description varchar(255) not null,
  detail text not null,
  lat float,
  lng float,
  beacon_id varchar(255),
  visitor_count int default 0,
  index idx_location(lat, lng)
);

-- ### keyword_relationships
create table if not exists keyword_relationships (
  id int not null primary key auto_increment,
  keyword_id int,
  store_id int,
  foreign key(keyword_id) references keywords(id),
  foreign key(store_id) references stores(id)
);

-- ### items
create table if not exists items (
  id int not null primary key auto_increment,
  store_id int,
  url text,
  label varchar(255),
  foreign key(store_id) references stores(id)
);
