## Create Database
```sql
create database resas2017;
use resas2017;
```

## Create Tables
### keywords
```sql
create table if not exists keywords (
  id int not null primary key auto_increment,
  keyword varchar(255) not null unique,
  index idx_keyword(keyword)
);
```

### stores
```sql
create table if not exists stores (
  id int not null primary key auto_increment,
  name varchar(255) not null unique,
  thumbnail text,
  description varchar(255) not null,
  detail text not null,
  lat float,
  lng float,
  beacon_id varchar(255),
  index idx_location(lat, lng)
);
```

### items
```sql
create table if not exists items (
  id int not null primary key auto_increment,
  store_id int,
  url text,
  description varchar(255),
  foreign key(store_id) references stores(id)
);
```
